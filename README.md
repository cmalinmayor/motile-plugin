# Motile Napari Plugin

[![tests](https://github.com/funkelab/motile-napari-plugin/workflows/tests/badge.svg)](https://github.com/funkelab/motile-napari-plugin/actions)
[![codecov](https://codecov.io/gh/funkelab/motile-napari-plugin/branch/main/graph/badge.svg)](https://codecov.io/gh/funkelab/motile-napari-plugin)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/motile-plugin)](https://napari-hub.org/plugins/motile-plugin)

A plugin for tracking with [motile](https://github.com/funkelab/motile) in napari. 
Motile is a library that makes it easy to solve tracking problems using optimization 
by framing the task as an Integer Linear Program (ILP).
See the motile [documentation](https://funkelab.github.io/motile) 
for more details on the concepts and method.

----------------------------------

## Installation

This plugin depends on [motile](https://github.com/funkelab/motile), which in 
turn depends on gurobi and ilpy. These dependencies must be installed with 
conda before installing the plugin with pip.

    conda create -n motile-plugin python>=3.10
    conda activate motile-plugin
    conda install -c conda-forge -c funkelab -c gurobi ilpy
    pip install git+https://github.com/funkelab/motile-napari-plugin.git

## Issues

If you encounter any problems, please 
[file an issue](https://github.com/funkelab/motile-napari-plugin/issues) 
along with a detailed description.
