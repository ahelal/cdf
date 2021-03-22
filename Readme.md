# CDF

## Install

* Install azure cli >= 2.20.0 + Python >= 3.7 
* For the current time you need to build the extension
    * `make venv` create python virtual environment-
    * `make install` this will build the extension and install

## uninstall

To uninstall the extension run `make uninstall`

## Help 

`az cdf --help`

Check the examples https://github.com/ahelal/cdf-examples

## Configuration 

TODO

### life cycle 


## Template

Standard jinja2 expressions are support https://jinja.palletsprojects.com/en/2.11.x/templates/. besides standard special variables and functions are supported

### Variables

* `env` to access environment variable. i.e. `{{ env['HOME'] }}` home directory in *nix
* `CDF_VERSION` CDF version 
* `CDF_TMP_DIR` CDF template directory path 
* `CONFIG_DIR` CDF configuration directory path. path to `.cdf.yml` directory
* `CONFIG_RESOURCE_GROUP` interpolated resource group 
* `PLATFORM` platform client machine is running i.e. Darwin, Linux, Windows

### Result

TODO

### Phases

TODO

## TODO

* Ability to save vars in state (for random strings example rg)
* HTTP get resource in jinja2
* Check if a deployment is running and connect instead of redeploying or deleting
* Tests :)
* Implement test handler and test lifecycle
* Support terraform
