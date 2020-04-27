# oda-tests

* KG keeps descriptions of workflows, describing for each:
  * an _execution workflow_  (another workflow, which takes workflow as an input)
  * inputs
  * location  
* tests are composed from KG descriptions of the available workflows and compatible inputs
* an additional "timestamp" input is added for each workflow, with pre-defined period
* composition is currying - workflow is transformed to that without inputs
* workflows without inputs can be executed by the relevant execution workflows
* workers are declaring ability to execute some execution workflows, fetching and 

Described [here](https://doi.org/10.5281/zenodo.3560567) and [here](https://doi.org/10.5281/zenodo.3559528).
