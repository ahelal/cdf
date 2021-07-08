
# TODO

* alpha release requirements
    * fix tests
    * support runner 
    * support plan 
    * better code coverage
    * improve docs

* Core
    * Improve logging system to inform user whats happening specifically for test
    * Add Scope tenet, and subscription
    * Add support to customize bicep, terraform binary path
* Test upgrade
    * Support what if in tests, and terraform changes,deletion, additions
    * Support dynamic calc in upgrades upgrade i.e. last hash, release before last
* Template
    * Add more tests/asserts for jinja2 (to check dir, file, and filter for json/yaml
    * HTTP get filter in jinja2
* Useability 
    * Status should attempt to reconcile with ARM and update real status
    * Check if a deployment is running and connect instead of redeploying or deleting
* Running CDF as service
    * Implement generic rest interface to run cdf by HTTP2
* Hooks
    * Support fire and forget mode in ops
    * Implement support for file in hooks to load hooks from file
* Tests
    * Package Azspec 
    * Save test results in state
    * Capture stdout, stderr in tests