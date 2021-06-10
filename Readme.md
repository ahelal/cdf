# CDF

## Overview

CDF is an Azure CLI plugin that will make your life easier to develop, test, maintain, share units, and run IaC code in Azure. currently supports IaC `ARM`, `bicep` and `terraform`.

## Install (Dev version)

* Install azure cli >= 2.20.0 + Python >= 3.7 
* For the current time you need to build the extension
    * `make venv` create python virtual environment-
    * `make install` this will build the extension and install

To uninstall the extension run `make uninstall`

## Quick start guide

TODO

## Configuration 

CDF uses a yaml based confutation file

```yaml
# Required, string, simple templatable. "Deployment name. Can't be changed after provisioning"
name: deployment_name
# Required, string, simple templatable. "The default resource group to deploy to"
resource_group: my_rg
# Optional, bool, not templatable, defaults to 'true'. "Create RG if it does not exist and delete on down"
manage_resource_group: true
# Required, string, simple templatable. "The default location to deploy to"
location: 'eastus'
# Optional, string, not templatable. "Only support resource_group for now"
scope: "resource_group"
# Optional, bool, not templatable. "Do a complete or incremental deployment"
complete_deployment: true
# Optional, string, not templatable. default to bicep, supports "bicep, arm, terraform"
provisioner: 'bicep'
# Optional, string, templatable defaults to *.bicep file in the same dir as `.cdf.yml` . "main Bicep file used for provisioning"
up: file.bicep

# Optional, string, simple templatable defaults to '{{CONFIG_DIR}}/.cdf_tmp'. "Temp directory needed to store CDF state and json files"
temp_dir: '{{CONFIG_DIR}}/.cdf_tmp'
# Optional, string, simple templatable defaults to '{{CDF_TMP_DIR}}/state.json'. "CDF state file"
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
  helloworld:
    description: "Optional description of hook"
    ops:  # list of Operations
      - type: print
        args: Running creating {{cdf.name}} in {{cdf.resource_group}}
```

### Hooks 

One useful functionality of CDF is hooks, You can create ad-hoc operation and call them manually or part of the lifecycle.
The ah-hoc commands are harder to incorporated part of your normal provisioning sequence. 
Some examples 
* ssh into a VM on demand
* Taking a snapshot now
* Downloading logs

hooks are defined in the `.cdf.yml` under `hooks` then the hook name.

```yaml
hooks:
  hook1:
      ...
  hook2:
      ...
  hook3:
      ...
```

Anatomy of hooks

```yaml
hooks:
  helloworld:
    description: "Optional description of hook"  # Optional, string, not templatable. default to ""
    ops:  
      # At least one op is required
      - name: opname # Optional, string, not templatable. if defined will store the output of the op operation and can be referenced later
        type: print # Optional, string, not templatable, defaults to `az` check type section
        args: Running creating {{cdf.name}} in {{cdf.resource_group}} # required, string, templatable. arguments for the op, each type handles arguments differently
        platform: 
        mode: wait # Optional, string, not templatable, defaults to `wait`, supported wait, interactive
        cwd: "/" # optional, string, templatable, defaults to current working directory
        platform: "linux" # Optional, string or list, not templatable, which platform this op can run
    lifecycle: ""  # Optional, string or list, not templatable. default to "", supports check lifecycle section
    run_if: true # Optional, string, templatable. default to "true", must be interpolated to string boolean i.e. "true", "TRUE", "0", "no", ..., support 
```

You can run hooks by issuing `az cdf hook <HOOK_NAME>`. 

if you want to pass argument to your hook you can use `{{args}}` variable.

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

#### Hook types

##### az

run az cli commands, this is the default hook type
notice you skip the `az` in the args and type the args directly

```yaml
  creds:
    description: "Get AKS creds"
    ops:
      - args: aks get-credentials --name {{ cdf.name }} --resource-group {{ cdf.resource_group}} --overwrite-existing
      - type: print
        args: "Your ready to use {{ cdf.name }}"
```

##### cmd

Run commands

```yaml
  run:
    ops:
      - name: Load and interpolate and execute script
        type: cmd
        args: curl -X POST -d '{"a":1}' https://www.example.com
```

##### script

Execute a script, The script will be loaded and interpolated first.

```yaml
  run:
    ops:
      - name: Load and interpolate and execute script
        type: script
        args:
          - "{{cdf.config_dir}}/script.sh"```
```
content of `script.sh`

```sh
#!/bin/sh
echo "{{ cdf.resource_group}}"
```

##### print

Print supplied args to stdout

```yaml
  log:
    ops:
      - type: print
        args: "This will be printed and will be interpolated {{cdf.name}}"
```

##### call

Call another hook

```yaml
  log:
    ops:
      - type: print
        args: "-> {{ args[1:] | join(' ') }}"
  call:
    ops:
        # will call log hook
      - type: call
        args: log
```

#### Life cycle 

TODO

#### Conditional execution 

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

If your code has `outputs` you can access them using `{{ result.outputs.YOUR_OUTPUT_NAME.value }}` after you provision. You can use them in any post up hooks. 
You can also access the `resources` created if your using `arm or bicep` provisioner using `{{ result.resources }}`

### Phases

TODO

## Tests

TODO

## Credentials in state

By default CDF does not store any credentials in cdf state file, but output, variables, errors, and parameters can be stored in state file. Also deployments, tmp files can be stored in `cdf.tmp_dir`
To avoid any potential credentials leakage you should git ignore the entire `cdf.tmp_dir`.

## Help 

`az cdf --help`

Check the examples https://github.com/ahelal/cdf-examples
