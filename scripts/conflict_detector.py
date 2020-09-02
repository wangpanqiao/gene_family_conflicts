import sys
import os
import argparse

import comparisons
import analysis
import make_trees
import read_trees
from objects import Node, Rel, Bipart

if __name__ == "__main__":
    # Taking user input.
    parser = argparse.ArgumentParser(
        description="A program to help find and analyse conflict and concordance in ortholog trees with duplications.")
    parser.add_argument("-d", "--description", action="store_true",
                        help="Gives a longer description of the program and different modes.")
    parser.add_argument("--species_tree", type=str,
                        help="A file containing the species tree.")
    parser.add_argument(
        "--mode", type=str, help="The mode that we run the program in. Should be n (normal), r (reverse) or s (search).")
    parser.add_argument("--gene_tree", type=str,
                        help="File containing a gene tree. Required in 'r' mode.")
    parser.add_argument("--gene_folder", type=str,
                        help="A folder containing all the gene trees to be analysed. Required for 'n' and 's' modes.")
    parser.add_argument("--cutoff", type=int, default=80,
                        help="Nodes with a bootstrap label below the cutoff value will not be included in the analysis.")
    parser.add_argument("--query_bipart", type=str,
                        help="A query to be searched. Required in 's' mode, should be entered in the form: 'taxon1,taxon2', NO SPACES.")
    parser.add_argument("--no_csv", action="store_true",
                        help="Program does not create a .csv file with a more detailed breakdown of the different conflict abundences.")
    parser.add_argument("--outfile_prefix", type=str, help="Outfile name.")

    if len(sys.argv) == 1:
        parser.print_usage()
        parser.exit()

    args = parser.parse_args()
    if args.description:
        print "This program shows gene tree conflict whilst accounting\n\
for duplication events in gene trees.\n\n\
Normal mode (specify mode as 'n') produces two outputs:\n\
the printed output shows two trees in newick format,\n\
showing the number of conflicts and concordances at each\n\
node as labels. It also outputs a tab-separated table\n\
showing a more detailed breakdown of the types of\n\
conflict at each node.\n\n\
reverse mode (specify mode as 'r') maps conflicts with\n\
the species tree back onto the user-specified gene tree,\n\
labelling concordance with '*', conflict with 'X' and a\n\
duplication node with 'D'.\n\n\
Search mode (specify mode as 's') allows the user to\n\
search for a specific bipart in a folder of gene trees,\n\
and returns a list of all the tree files that contain\n\
that bipart."
        sys.exit(0)

    mode = args.mode
    species_tree = args.species_tree
    cutoff = args.cutoff
    gene_folder = args.gene_folder
    gene_tree = args.gene_tree
    query_bipart = args.query_bipart
    outfile_prefix = args.outfile_prefix

    if mode == 'n':
        # Check we have arguments required.
        if not species_tree or not gene_folder:
            print "--species_tree and --gene_folder are required arguments in this mode."
            sys.exit(0)

        # Making the species tree.
        tree_file = open(species_tree, "r")
        for line in tree_file:
            tree = line
        species_root, species_name_array = make_trees.build(tree)
        species_biparts = read_trees.postorder2(species_root)
        all_taxa = read_trees.postorder3(species_root)
        species_biparts.append(all_taxa)

        # We need these later.
        total_conflicts = []
        total_concordances = []

        # Making sure folder always has the same name.
        if gene_folder[-1] == '/':
            homologs_folder = gene_folder
        else:
            homologs_folder = gene_folder + '/'

        # Because we do all the work inside this for loop, we use less
        # memory as we only handle one file at once.
        file_list = os.listdir(homologs_folder)
        len_file_list = str(len(file_list))
        file_no = 0
        for file in file_list:
            file_no += 1
            sys.stderr.write("Processing file " + str(file_no) +
                             " of " + len_file_list + ".\r")

            # Building the gene tree.
            file_location = str(homologs_folder) + str(file)
            gene_file = open(file_location, "r")

            for line in gene_file:
                tree = line
                gene_root, gene_name_array = make_trees.build(tree)

                # We make 'subtrees' to deal with the problem of
                # duplication: the subtrees contain no duplications and
                # cover the whole gene tree.
                trees = make_trees.subtrees_function(gene_root)
                log_name = gene_folder[:-1] + "_subtree_comp.log"

                # This catches *most* of the conflicts and concordances.
                for tree in trees:
                    conflicts, concordances = comparisons.compare_trees(
                        species_biparts, species_name_array, tree, mode, "some_log_name", cutoff)
                    total_concordances.extend(concordances)

                    # We only use one conflict per gene (accounting for nesting).
                    filtered_conflicts = comparisons.filter_conflicts(
                        conflicts)
                    total_conflicts.extend(filtered_conflicts)

                # A small number of non-duplication nodes on each gene
                # tree can be missed by the subtree method, and we need
                # to acccount for these.
                tricky_nodes = read_trees.identify_tricky_nodes(
                    gene_root, trees)
                conflicts = []
                for node in tricky_nodes:
                    node_bipart = read_trees.postorder3(node)
                    node_biparts = [node_bipart]
                    node_name_array = read_trees.postorder3(node)
                    node_name_array = node_name_array.bipart_proper

                    # Making an appropriate name array as we need to
                    # include all the names from just upstream of
                    # the node.
                    new_names = []
                    current_node = node
                    while True:
                        parent = current_node.parent
                        if parent == None:
                            break

                        make_trees.label_duplications(parent, recursive=False)
                        if parent.label == 'D':
                            current_node = parent
                        else:
                            for child in parent.children:
                                if child != current_node:
                                    new_names = read_trees.postorder3(child)
                                    new_names = new_names.bipart_proper
                            break
                    node_name_array.extend(new_names)

                    # Adding the tricky nodes to conflicts and
                    # concordances.
                    log_name = gene_folder[:-1] + "_tricky_nodes_comp.log"
                    rel_list = comparisons.comp_biparts(
                        species_biparts, node_biparts, species_name_array, node_name_array, log_name, cutoff, mode)
                    for rel in rel_list:
                        if rel.relation == 'conflict':
                            total_conflicts.append(rel)
                        elif rel.relation == 'concordant':
                            total_concordances.append(rel)
        if not args.no_csv:
            # Extra analysis to get the relative frequenices of the
            # conflicts, etc.
            outfile = open(homologs_folder[:-1] + "_analysis.csv", "w")
            sorted_conflicts = analysis.sort_conflicts(total_conflicts)
            analysis.conflict_stats(sorted_conflicts, species_root, outfile)

        if outfile_prefix:
            concord_out = open(str(outfile_prefix) + "_concord.tre", "w")
            conflict_out = open(str(outfile_prefix) + "_conflict.tre", "w")
            labels_out = open(str(outfile_prefix) + "_labels.tre", "w")
        else:
            concord_out = open("out_concord.tre", "w")
            conflict_out = open("out_conflict.tre", "w")
            labels_out = open("out_labels.tre", "w")

        # Map concordances and conflicts back onto the tree using the lists
        print "\n"
        make_trees.clear_labels(species_root)
        make_trees.tree_map(species_root, total_concordances)
        make_trees.add_zeros(species_root)
        concordance_tree = species_root.get_newick_repr(showbl=True)
        print "Concordance tree: "
        print concordance_tree + ";"
        concord_out.write(concordance_tree + ";")

        make_trees.clear_labels(species_root)
        make_trees.tree_map(species_root, total_conflicts)
        make_trees.add_zeros(species_root)
        conflict_tree = species_root.get_newick_repr(showbl=True)
        print "Conflict tree:"
        print conflict_tree + ";"
        conflict_out.write(conflict_tree + ";")

        make_trees.label_node_ids(species_root)
        labels_tree = species_root.get_newick_repr(showbl=True)
        print "Labels tree: "
        print labels_tree + ";"
        labels_out.write(labels_tree + ";")

    elif mode == "r":
        # Checking we have the right arguments.
        if not species_tree or not gene_tree:
            print "--species_tree and --gene_tree are required arguments in this mode."
            sys.exit()

        # Again, we start by reading in the species tree.
        file = open(species_tree, "r")
        for line in file:
            tree = line
        species_root, species_name_array = make_trees.build(tree)
        species_biparts = read_trees.postorder2(species_root)
        all_taxa = read_trees.postorder3(species_root)
        species_biparts.append(all_taxa)

        # Then we read in the gene tree.
        file = open(gene_tree, "r")
        counter = 0
        for line in file:
            tree = line
            counter += 1
        if counter != 1:
            print "There must be only one tree in the gene tree file!"
            sys.exit()
        gene_root, gene_name_array = make_trees.build(tree)
        trees = make_trees.subtrees_function(gene_root)

        if len(trees) != 0:
            outfile = gene_tree + "_subtree_comp.log"
            for tree in trees:
                conflicts, concordances = comparisons.compare_trees(
                    species_biparts, species_name_array, tree, mode, outfile, cutoff)
                make_trees.tree_map2(tree, conflicts, "X")
                make_trees.tree_map2(tree, concordances, "*")


           
            # As in normal mode, there are some nodes missed by the
            # subtree method.
            tricky_nodes = read_trees.identify_tricky_nodes(gene_root, trees)
            conflicts = []
            concordances = []

            for node in tricky_nodes:
                node_bipart = read_trees.postorder3(node)
                node_bipart_list = [node_bipart]
                node_name_array = read_trees.postorder3(node)
                node_name_array = node_name_array.bipart_proper
                new_names = []
                current_node = node

                while True:
                    parent = current_node.parent
                    if parent != None:
                        make_trees.label_duplications(parent, recursive=False)
                        if parent.label == 'D':
                            current_node = parent
                        elif type(parent) is None:
                            break
                        else:
                            for child in parent.children:
                                if child != current_node:
                                    new_names = read_trees.postorder3(child)
                                    new_names = new_names.bipart_proper
                            break
                    else:
                        break
                
                node_name_array.extend(new_names)
            	outfile = gene_tree + "_tricky_nodes_comp.log"
            	rel_list = comparisons.comp_biparts(
                    node_bipart_list, species_biparts, node_name_array, species_name_array, outfile, cutoff, mode)

            	for rel in rel_list:
                	if rel.relation == 'conflict':
                		conflicts.append(rel)
                	elif rel.relation == 'concordant':
						concordances.append(rel)
			
            # Printing the output.
            make_trees.tree_map2(gene_root, conflicts, 'X')
            make_trees.tree_map2(gene_root, concordances, '*')
            make_trees.label_duplications(gene_root)
            make_trees.label_uninformative(gene_root)
            make_trees.add_loci(gene_root)
            new_tree = gene_root.get_newick_repr(showbl=True)
            #print new_tree + ";"
            if outfile_prefix:
                out = open(str(outfile_prefix) + "_concon.tre", "w")
                labels = open(str(outfile_prefix) + "_labels.tre", "w")
            else:
                out = open("concon.tre", "w")
                labels = open("labels.tre", "w")
            out.write(new_tree + ";")
            make_trees.label_node_ids(gene_root)
            labels_tree = gene_root.get_newick_repr(showbl=True)
            labels.write(labels_tree + ";")
        else:
            # It's a lot simpler when there are no duplications.
            outfile = gene_tree + "_comp.log"
            conflicts, concordances = comparisons.compare_trees(
                species_biparts, species_name_array, gene_root, mode, outfile, cutoff, mode)
            make_trees.tree_map2(gene_root, conflicts, 'X')
            make_trees.tree_map2(gene_root, concordances, '*')
            make_trees.label_duplications(gene_root)
            make_trees.label_uninformative(gene_root)
            make_trees.add_loci(gene_root)
            new_tree = gene_root.get_newick_repr(showbl=True)
            print new_tree + ";"
            if outfile_prefix:
                out = open(str(outfile_prefix) + "_concon.tre", "w")
                labels = open(str(outfile_prefix) + "_labels.tre", "w")
            else:
                out = open("concon.tre", "w")
                labels = open("labels.tre", "w")
            out.write(new_tree + ";")
            make_trees.label_node_ids(gene_root)
            labels_tree = gene_root.get_newick_repr(showbl=True)
            labels.write(labels_tree + ";")

    elif mode == 's':
        # Checking arguments.
        if not gene_folder or not query_bipart:
            print "--gene_folder and --query_bipart are required arguments in this mode."
            sys.exit()

        # We need these for later.
        concordant_files = []

        # Putting the query into a form comp_biparts likes.
        query_entered = query_bipart.split(",")
        query = Bipart("query", "query")
        for taxon in query_entered:
            query.add_taxon(taxon)
        query_name_array = query_entered

        # Opening and reading the provided folder of homologs.
        if gene_folder[-1] == "/":
            homologs_folder = gene_folder
        else:
            homologs_folder = gene_folder + "/"
        file_list = os.listdir(homologs_folder)

        for filename in file_list:
            total_concordances = []
            sys.stderr.write("processing " + str(filename) + '\r')

            # Building a tree and making subtrees.
            file_location = str(homologs_folder) + str(filename)
            file = open(file_location, "r")
            for line in file:
                tree = line
            gene_root, gene_name_array = make_trees.build(tree)
            trees = make_trees.subtrees_function(gene_root)

            # Looking for concordances in the subtrees.
            outfile = gene_folder[:-1] + "_comp.log"
            for tree in trees:
                concordances = []
                conflicts, concordances = comparisons.compare_trees(
                    [query], query_name_array, tree, mode, outfile, cutoff)
                total_concordances.extend(concordances)

            # Dealing with the nodes that aren't in subtrees again.
            tricky_nodes = read_trees.identify_tricky_nodes(gene_root, trees)
            for node in tricky_nodes:
                concordances = []
                node_bipart = read_trees.postorder3(node)
                node_bipart_list = [node_bipart]
                node_name_array = read_trees.postorder3(node)
                node_name_array = node_name_array.bipart_proper

                new_names = []
                current_node = node
                while True:
                    parent = current_node.parent
                    if parent == None:
                        break

                    make_trees.label_duplications(parent, recursive=False)
                    if parent.label == 'D':
                        current_node = parent
                    else:
                        for child in parent.children:
                            if child != current_node:
                                new_names = read_trees.postorder3(child)
                                new_names = new_names.bipart_proper
                        break

                node_name_array.extend(new_names)
                outfile = gene_folder[:-1] + "_tricky_nodes_comp.log"
                rel_list = comparisons.comp_biparts(
                    [query], node_bipart_list, query_name_array, node_name_array, outfile, cutoff, mode)

                for rel in rel_list:
                    if rel.relation == 'concordant':
                        concordances.append(rel)

                total_concordances.extend(concordances)

            # We add all files with any concordances to the list.
            for i in range(len(total_concordances)):
                concordant_files.append(filename)

        # Printing the list of files concordant.
        print "\n"
        for file in concordant_files:
            print str(file)

        number_of_times = len(concordant_files)
        concordant_set = set(concordant_files)
        total_files = len(concordant_set)

        # Printing the total length of the list.
        print "Relationship " + str(query_bipart) + " appears " + str(number_of_times) + \
            " times in " + str(total_files) + " genes of " + \
            str(len(file_list)) + " total genes."
