# ODA Experiments: dynamic workflow composition for testing, experiments, and publishing

## Intro

Is it just another WMS? Note really.

We leverage workflows description as simple computable expressions. Translatable in and interoperable with other workflow descriptions (CWL) including WMS-specific ones.

Meta-WMS for interfacing with different specific engines.


##

Experiments are end-to-end live platform *tests* as well as other workflows constructed from those available in the KB.

* KG keeps descriptions of workflows, describing for each:
  * an _execution workflow_  (another workflow, which takes workflow as an input)
  * inputs
  * location  
* tests are composed from KG descriptions of the available workflows and compatible inputs
* an additional "timestamp" input is added for each workflow, with pre-defined period
* composition is currying - workflow is transformed to that without inputs
* workflows without inputs can be executed by the relevant execution workflows
* each execution yeilds a _fact_, a statement of equivalence (established by the means of particular classified executur) between an executable workflow and stored data.
* workers are declaring ability to execute some execution workflows.

The tests are used to derive available _platform features_, e.g. "platform is able to produce ISGRI images for old data".
The features are constructed with reasoning rules from a collection of facts produced by tests.


Described [here](https://doi.org/10.5281/zenodo.3560567) and [here](https://doi.org/10.5281/zenodo.3559528).


## Other similar options

https://hypothesis.readthedocs.io/en/latest/

Program synthesis  https://synthesis.to/papers/phd_thesis.pdf

