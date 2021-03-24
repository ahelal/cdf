# CDF

## Overview

TODO

## Install

* Install azure cli >= 2.20.0 + Python >= 3.7 
* For the current time you need to build the extension
    * `make venv` create python virtual environment-
    * `make install` this will build the extension and install

## uninstall

To uninstall the extension run `make uninstall`

## Configuration 

CDF uses a yaml based confutation file

```yaml
# Required, string, templatable. "Deployment name. Can't be changed after provisioning"
name: deployment_name
# Required, string, templatable. "The default resource group to deploy to"
resource_group: myrg
# Optional, bool, not templatable, defaults to 'true'. "Create RG if it does not exist and delete on down"
manage_resource_group: true
# Required, string, templatable. "The default location to deploy to"
location: 'eastus'
# Optional, string, templatable. "Only support resource_group for now"
scope: "resource_group"
# Optional, bool, not templatable. "Do a complete or incremental deployment"
complete_deployment: true
# Optional, string, not templatable. "At the moment only bicep is supported"
provisioner: 'bicep'
# Optional, string, templatable defaults to *.bicep file in the same dir as `.cdf.yml` . "main Bicep file used for provisioning"
up: file.bicep

# Optional, string, templatable defaults to '{{CONFIG_DIR}}/.cdf_tmp'. "Temp directory needed to store CDF state and json files"
temp_dir: '{{CONFIG_DIR}}/.cdf_tmp'
# Optional, string, templatable defaults to '{{CDF_TMP_DIR}}/state.json'. "CDF state file"
state: '{{ CDF_TMP_DIR }}/state.json'

# optional, object, templatable defaults to {}. "Parameters that will be passed on to the provisioner"
params:
  location: eastus
  name: openvpn

# optional, object, templatable defaults to {}. "variables that can be used as reusable reference inside the interpolation"
# See variable session
vars:
  adminPasswordOrKey: '~/.ssh/id_rsa'
  nsg_name: "ssh_nsg"

# optional, object, templatable defaults to {}.
# See hooks section
hooks:
    hello:
        type: print
        args: 'Hello'
```

### Hooks 

TODO

### life cycle 

TODO

## Template

Standard jinja2 expressions are support https://jinja.palletsprojects.com/en/2.11.x/templates/. besides standard special variables and functions are supported

### Variables

* `env` to access environment variable. i.e. `{{ env['HOME'] }}` home directory in *nix
* `CDF_VERSION` CDF version 
* `CDF_TMP_DIR` CDF template directory path 
* `CONFIG_DIR` CDF configuration directory path. path to `.cdf.yml` directory
* `CONFIG_RESOURCE_GROUP` interpolated resource group 
* `PLATFORM` platform client machine is running i.e. Darwin, Linux, Windows

### Filters

Besides common filters in jinja2 https://jinja.palletsprojects.com/en/2.11.x/templates/#list-of-builtin-filters a few has been added

* `include_file` include static content of a file i.e `mycontent: {{ include_file('path/file.txt') }}`
* `template_file` include and interpolate the content a file i.e `users: {{ template_file('path/users.yaml') }}`

### Result

TODO

### Phases

TODO

## Help 

`az cdf --help`

Check the examples https://github.com/ahelal/cdf-examples

## TODO

* Fix output table bug `cdf hook -o table`
* Params and var files in cdf
* Create a reference to `CONFIG` i.e. `config.resource_group` or `config.location` 
* Ability to save vars in state (for random strings example rg)
* HTTP get resource in jinja2
* Tests :)
* Implement test handler and test lifecycle
* Support terraform
* Check if a deployment is running and connect instead of redeploying or deleting
* Support interactive cmd bind stdout,stderr, stdin
