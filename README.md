# oda-tests

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
