
# TODO

* Implement logging system to inform user whats happening specifically for test
* Implement support for file in hooks to load hooks from file
* Save test results in state
* Support commit hash in upgrade, support dynmaic last commit math ~
* Lock during ops and hooks to avoid double run
* change the filename from targetfile to deployment name in bicep deployment
* Add more tests/asserts for jinja2 (to check dir, file, and filter for json/yaml
* Capture stdout, stderr in tests
* HTTP get filter in jinja2
* Status should attempt to reconcile with ARM and update real status
* Check if a deployment is running and connect instead of redeploying or deleting
* Implement generic rest interface to run cdf by HTTP2
* Support fire and forget mode in ops