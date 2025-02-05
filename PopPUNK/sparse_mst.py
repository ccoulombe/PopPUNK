#!/usr/bin/env python
# vim: set fileencoding=<utf-8> :
# Copyright 2018-2021 John Lees and Nick Croucher

# universal
import os
import sys

import pickle
import re
import numpy as np
import pandas as pd
from scipy import sparse

# Load GPU libraries
try:
    import cupyx
    import cugraph
    import cudf
    import cupy as cp
    from numba import cuda
    import rmm
    gpu_lib = True
except ImportError as e:
    gpu_lib = False

# import poppunk package
from .__init__ import __version__

from .network import cugraph_to_graph_tool
from .network import save_network
from .network import network_to_edges
from .network import generate_minimum_spanning_tree
from .network import construct_network_from_sparse_matrix

from .plot import drawMST

from .trees import mst_to_phylogeny, write_tree

from .utils import setGtThreads, readIsolateTypeFromCsv
from .utils import check_and_set_gpu
from .utils import read_rlist_from_distance_pickle

# command line parsing
def get_options():

    import argparse

    parser = argparse.ArgumentParser(description='Create a minimum-spanning tree',
                                     prog='poppunk_mst')

    # input options
    iGroup = parser.add_argument_group('Input files')
    iGroup.add_argument('--rank-fit', required=True, help='Location of rank fit, a sparse matrix (*_rank*_fit.npz)')
    iGroup.add_argument('--previous-clustering', help='CSV file with cluster definitions')
    iGroup.add_argument('--previous-mst', help='Graph tool file from which previous MST can be loaded',
                                            default=None)
    iGroup.add_argument('--distance-pkl', help='Input pickle from distances, which contains sample names')
    iGroup.add_argument('--previous-distance-pkl', help='Input pickle from distances, which contains sample names')
    iGroup.add_argument('--display-cluster', default=None, help='Column of clustering CSV to use for plotting')

    # output options
    oGroup = parser.add_argument_group('Output options')
    oGroup.add_argument('--output', required=True, help='Prefix for output files (required)')
    oGroup.add_argument('--no-plot', default=False, action='store_true',
                        help='Do not try and draw the MST')

    # processing
    other = parser.add_argument_group('Other options')
    other.add_argument('--threads', default=1, type=int,
                       help='Number of threads to use [default = 1]')
    other.add_argument('--gpu-graph', default=False, action='store_true',
                       help='Use cugraph for the calculation')

    other.add_argument('--version', action='version',
                       version='%(prog)s '+__version__)

    return parser.parse_args()

def generate_mst_from_sparse_input(sparse_mat, rlist, old_rlist = None, previous_mst = None, gpu_graph = False):
    if gpu_graph:
        # Load previous MST if specified
        if previous_mst is not None:
            extra_sources, extra_targets, extra_weights = network_to_edges(previous_mst,
                                                                                  rlist,
                                                                                  old_ids = old_rlist,
                                                                                  weights = True,
                                                                                  use_gpu = gpu_graph)
            sources = np.append(sparse_mat.row, np.asarray(extra_sources))
            targets = np.append(sparse_mat.col, np.asarray(extra_targets))
            weights = np.append(sparse_mat.data, np.asarray(extra_weights))
        else:
            sources = sparse_mat.row
            targets = sparse_mat.col
            weights = sparse_mat.data
        G_df = cudf.DataFrame({'source': sources,
                               'destination': targets,
                               'weights': weights})
        G_cu = cugraph.Graph()
        G_cu.from_cudf_edgelist(G_df, edge_attr='weights', renumber=False)

        # Generate minimum spanning tree
        G = cugraph.minimum_spanning_tree(G_cu, weight='weights')
    else:
        # Load previous MST if specified
        if previous_mst is not None:
            G = construct_network_from_sparse_matrix(rlist,
                                                        rlist,
                                                        sparse_mat,
                                                        summarise=False,
                                                        previous_network = previous_mst)
        else:
            G = construct_network_from_sparse_matrix(rlist,
                                                        rlist,
                                                        sparse_mat,
                                                        summarise=False)
        sys.stderr.write("Calculating MST (CPU)\n")

    G = generate_minimum_spanning_tree(G, gpu_graph)
    
    return(G)


def main():

    # Check input args ok
    args = get_options()

    import graph_tool.all as gt
    # load CUDA libraries
    args.gpu_graph = check_and_set_gpu(args.gpu_graph, gpu_lib)

    # Read in sample names
    if (args.distance_pkl is not None) ^ (args.previous_clustering is not None):
        sys.stderr.write("To label strains, both --distance-pkl and --previous-clustering"
                         " must be provided\n")
        sys.exit(1)
    elif os.path.exists(args.distance_pkl):
        rlist = read_rlist_from_distance_pickle(args.distance_pkl,
                                                allow_non_self = False)
    else:
        sys.stderr.write("Cannot find file " + args.distance_pkl + "\n")
        sys.exit(1)

    # Read in old sequence names
    old_rlist = None
    if args.previous_distance_pkl is not None and os.path.exists(args.previous_distance_pkl):
        old_rlist = read_rlist_from_distance_pickle(args.previous_distance_pkl,
                                                    allow_non_self = False)

    # Check output path ok
    if not os.path.isdir(args.output):
        try:
            os.makedirs(args.output)
        except OSError:
            sys.stderr.write("Cannot create output directory\n")
            sys.exit(1)
    setGtThreads(args.threads)

    # Create network with sparse dists
    sys.stderr.write("Loading distances into graph\n")
    sparse_mat = sparse.load_npz(args.rank_fit)
    G = generate_mst_from_sparse_input(sparse_mat,
                                        rlist,
                                        old_rlist = old_rlist,
                                        previous_mst = args.previous_mst,
                                        gpu_graph = args.gpu_graph)

    # Save output
    sys.stderr.write("Generating output\n")
    save_network(G, prefix = args.output,
                    suffix = '_MST',
                    use_graphml = True,
                    use_gpu = args.gpu_graph)
    mst_as_tree = mst_to_phylogeny(G, rlist, use_gpu = args.gpu_graph)
    write_tree(mst_as_tree, args.output, "_MST.nwk", overwrite = True)

    # Make plots
    if not args.no_plot:

        # Convert cugraph to graph-tool for graphml saving
        # and add IDs as vertex labels
        if args.gpu_graph:
            G = cugraph_to_graph_tool(G, isolateNameToLabel(rlist))
            
        # Parse clustering
        if args.previous_clustering != None:
            mode = "clusters"
            if args.previous_clustering.endswith('_lineages.csv'):
                mode = "lineages"
            isolateClustering = readIsolateTypeFromCsv(args.previous_clustering,
                                                       mode = mode,
                                                       return_dict = True)
        else:
            # Create dictionary with everything in the same cluster if none passed
            isolateClustering = {'Cluster': {}}
            for v in mst.vertices:
                isolateClustering['Cluster'][G.vp.id[v]] = '0'

        # Check selecting clustering type is in CSV
        clustering_name = 'Cluster'
        if args.display_cluster != None and args.previous_clustering != None:
            if args.display_cluster not in isolateClustering.keys():
                sys.stderr.write('Unable to find clustering column ' + args.display_cluster + ' in file ' +
                                 args.previous_clustering + '\n')
                sys.exit()
            else:
                clustering_name = args.display_cluster
        else:
            clustering_name = list(isolateClustering.keys())[0]

        # Draw MST
        drawMST(G, args.output, isolateClustering, clustering_name, True)

    sys.exit(0)

