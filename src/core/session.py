import argparse

import onnxruntime


def build_session_options(args: argparse.Namespace) -> onnxruntime.SessionOptions:
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = args.intra_op_threads
    options.inter_op_num_threads = args.inter_op_threads
    options.enable_cpu_mem_arena = args.enable_cpu_mem_arena
    options.enable_mem_pattern = args.enable_mem_pattern
    options.enable_profiling = args.debug
    options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
    return options
