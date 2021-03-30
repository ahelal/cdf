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
resource_group: my_rg
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

### Hooks args

You can also pass extra arguments to your hook 

```yaml
hooks:
  info:
    ops:
    - type: print
      args: "All {{args}}\nHook={{args[0]}} First={{args[1]}} Second={{args[2]}}"
```
```sh
az cdf hook info option1 option2
## output
All ['info', 'option1', 'option2']
Hook=info First=option1 Second=option2
```

### life cycle 

TODO

## Template

Standard jinja2 expressions are support https://jinja.palletsprojects.com/en/2.11.x/templates/. besides standard special variables and functions are supported

### Variables

#### Built in variables

* `env` to access environment variable. i.e. `{{ env['HOME'] }}` home directory in *nix
* `cdf.name` CDF deployment name
* `cdf.version` CDF version 
* `cdf.tmp_dir` CDF template directory path 
* `cdf.config_dir` CDF configuration directory path. path to `.cdf.yml` directory
* `cdf.resource_group` interpolated resource group 
* `cdf.platform` platform client machine is running i.e. Darwin, Linux, Windows
* `cdf.location` CDF Azure's Location 

### Filters

Besides common filters in jinja2 https://jinja.palletsprojects.com/en/2.11.x/templates/#list-of-builtin-filters a few has been added

* `include_file('filepath')` include static content of a file i.e `my_content: {{ include_file('path/file.txt') }}`
* `template_file('filepath')` include and interpolate the content a file i.e `users: {{ template_file('path/users.yaml') }}`
* `random_string(length, options=[])` create a random string of a given length, You can specify the type string as an array of string i.e. `random_string(10, options=['lower','upper'])`
  * upper: Upper case string
  * lower: Lower case string
  * numbers: Digits 0-9
  * special: Printable special chars
  * all: all of the above
* `store(key, value)` store the value in a key in the state file, Can be used to create random, strings, password, ... and save them between runs `store('postfix', random_string(6, 'lower'))"`

### Result

TODO

### Phases

TODO

## Help 

`az cdf --help`

Check the examples https://github.com/ahelal/cdf-examples

## TODO

* add jinja2 test to check dir, file , and filter for json/yaml
* Refactor to remove access to state directly and use config 
* Tests :)
* Support terraform
* Implement test handler and test lifecycle
* Implement generic rest interface 
* Check if a deployment is running and connect instead of redeploying or deleting
* HTTP get filter in jinja2
