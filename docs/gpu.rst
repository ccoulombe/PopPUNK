Using GPUs
==========

PopPUNK can use GPU acceleration of sketching (only when using sequence reads), distance
calculation, network construction and some aspects of visualisation. Installing and
configuring the required packages necessitates some extra steps, outlined below.

Installing GPU packages
-----------------------
To use GPU acceleration, PopPUNK uses cupy, numba and packages from RAPIDS. Both
cupy and numba can be installed as standard packages using conda. To install RAPIDS,
see the `guide <https://rapids.ai/start.html#get-rapids>`__. We would recommend
installing into a clean conda environment with a command such as::

    conda create -n poppunk_gpu -c rapidsai -c nvidia -c conda-forge \
    -c bioconda -c defaults rapids=0.17 python=3.8 cudatoolkit=11.0 \
    pp-sketchlib>=1.6.2 poppunk>=2.3.0 networkx cupy numba
    conda activate poppunk_gpu

The version of pp-sketchlib on conda only supports some GPUs. If this doesn't work
for you, it is possible to install from source. Add the build dependencies to your
conda environment::

    conda install cmake pybind11 highfive Eigen armadillo openblas libgomp libgfortran-ng


.. note::

    On OSX replace ``libgomp libgfortan-ng`` with ``llvm-openmp gfortran_impl_osx-64``,
    and remove ``libgomp`` from ``environment.yml``.

Clone the sketchlib repository::

    git clone https://github.com/johnlees/pp-sketchlib.git
    cd pp-sketchlib

Edit the ``CMakeLists.txt`` if necessary to change the compute version used by your GPU.
See `the CMAKE_CUDA_COMPILER_VERSION section <https://github.com/johnlees/pp-sketchlib/blob/master/CMakeLists.txt#L65-L68>`__.

.. table:: GPU compute versions
   :widths: auto
   :align: center

   ==================  =================
    GPU                Compute version
   ==================  =================
   20xx series         75
   30xx series         86
   V100                70
   A100                80
   ==================  =================

Make sure you have CUDA toolkit installed (this is available via conda as ``cudatoolkit``)
and ``nvcc`` is on your PATH::

    export PATH=/usr/local/cuda-11.1/bin${PATH:+:${PATH}}
    export LD_LIBRARY_PATH=/usr/local/cuda-11.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}

Then run::

    python setup.py install

You should see a message that the CUDA compiler is found, in which case the compilation
and installation of sketchlib will include GPU components::

    -- Looking for a CUDA compiler
    -- Looking for a CUDA compiler - /usr/local/cuda-11.1/bin/nvcc
    -- CUDA found, compiling both GPU and CPU code
    -- The CUDA compiler identification is NVIDIA 11.1.105
    -- Detecting CUDA compiler ABI info
    -- Detecting CUDA compiler ABI info - done
    -- Check for working CUDA compiler: /usr/local/cuda-11.1/bin/nvcc - skipped
    -- Detecting CUDA compile features
    -- Detecting CUDA compile features - done

You can confirm that your custom installation of sketchlib is being used by checking
the location of sketchlib library reported by ``popppunk`` points to your python
site-packages, rather than the conda version.

Selecting a GPU
---------------
A single GPU will be selected on systems where multiple devices are available. For
sketching and distance calculations, this can be specified by the ``--deviceid`` flag.
Alternatively, all GPU-enabled functions will used device 0 by default. Any GPU can
be set to device 0 using the system ``CUDA_VISIBLE_DEVICES`` variable, which can be set
before running PopPUNK; e.g. to use GPU device 1::

    export CUDA_VISIBLE_DEVICES=1

Using a GPU
-----------
By default, PopPUNK will use not use GPUs. To use them, you will need to add
the flag ``--gpu-sketch`` (when constructing or querying a database using reads),
``--gpu-dist`` (when constructing or querying a database from assemblies or reads),
or ``--gpu-graph`` (when querying or visualising a database, or fitting a model).
