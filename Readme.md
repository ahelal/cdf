# CDF

## Install

* Install azure cli >= 2.20.0 + Python >= 3.7 
* For the current time you need to build the extension
    * `make venv` create python virtual environment-
    * `make install` this will build the extension and install

## un-install

un-install extension `make uninstall`

## Help 

`az cdf --help`

Check the examples https://github.com/ahelal/cdf-examples

## TODO

* HTTP get resource in jinja2
* random string save in state
* Check if a deployment is running and connect instead of redeploying or deleting 
* Add a manage_resource_group option and create/delete if true defaults to true
* Add events to trigger lifecycle 
