===============
TomoTwin plugin
===============

This plugin provides a wrapper for `TomoTwin <https://github.com/MPI-Dortmund/tomotwin-cryoet>`_ software: Particle picking in Tomograms using triplet networks and metric learning

.. image:: https://img.shields.io/pypi/v/scipion-em-tomotwin.svg
        :target: https://pypi.python.org/pypi/scipion-em-tomotwin
        :alt: PyPI release

.. image:: https://img.shields.io/pypi/l/scipion-em-tomotwin.svg
        :target: https://pypi.python.org/pypi/scipion-em-tomotwin
        :alt: License

.. image:: https://img.shields.io/pypi/pyversions/scipion-em-tomotwin.svg
        :target: https://pypi.python.org/pypi/scipion-em-tomotwin
        :alt: Supported Python versions

.. image:: https://img.shields.io/sonar/quality_gate/scipion-em_scipion-em-tomotwin?server=https%3A%2F%2Fsonarcloud.io
        :target: https://sonarcloud.io/dashboard?id=scipion-em_scipion-em-tomotwin
        :alt: SonarCloud quality gate

.. image:: https://img.shields.io/pypi/dm/scipion-em-tomotwin
        :target: https://pypi.python.org/pypi/scipion-em-tomotwin
        :alt: Downloads

Installation
-------------

You will need to use 3.0+ version of Scipion to be able to run these protocols. To install the plugin, you have two options:

a) Stable version

.. code-block::

   scipion installp -p scipion-em-tomotwin

b) Developer's version

   * download repository

    .. code-block::

        git clone -b devel https://github.com/scipion-em/scipion-em-tomotwin.git

   * install

    .. code-block::

       scipion installp -p /path/to/scipion-em-tomotwin --devel

TomoTwin software will be installed automatically with the plugin but you can also use an existing installation by providing *TOMOTWIN_ENV_ACTIVATION* (see below).

**Important:** you need to have conda (miniconda3 or anaconda3) pre-installed to use this program.

Configuration variables
-----------------------
*CONDA_ACTIVATION_CMD*: If undefined, it will rely on conda command being in the
PATH (not recommended), which can lead to execution problems mixing scipion
python with conda ones. One example of this could can be seen below but
depending on your conda version and shell you will need something different:
CONDA_ACTIVATION_CMD = eval "$(/extra/miniconda3/bin/conda shell.bash hook)"

*TOMOTWIN_ENV_ACTIVATION* (default = conda activate tomotwin-0.1.2):
Command to activate the TomoTwin environment.

*NAPARI_ENV_ACTIVATION* (default = conda activate napari):
Command to activate the Napari viewer (boxmanager) environment.

Verifying
---------
To check the installation, simply run the following Scipion test:

``scipion test tomotwin.tests.test_protocols_tomotwin.TestTomoTwinRefPicking``

Supported versions
------------------

0.1.2

Protocols
----------

* reference-based picking

References
-----------

1. TomoTwin: Generalized 3D Localization of Macromolecules in Cryo-electron Tomograms with Structural Data Mining. Gavin Rice, Thorsten Wagner, Markus Stabrin, Stefan Raunser. https://www.biorxiv.org/content/10.1101/2022.06.24.497279v1
