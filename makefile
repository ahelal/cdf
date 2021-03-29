# define the name of the virtual environment directory
VENV := venv
#
EXTENTION_NAME := cdf
# default target, when make executed without arguments
all: source-venv

source-venv: $(VENV)/bin/activate

venv:
	python3 -m venv $(VENV)
	pip3 install -r dev-requirements.txt

build: source-venv clean
	python3 setup.py bdist_wheel

uninstall: 
	az extension remove -n $(EXTENTION_NAME)&& echo "Removing installed extention!" || echo "Extention not installed ignoring!" 

install: build uninstall
	az extension add --upgrade -y --source ./dist/$(EXTENTION_NAME)*.whl

test-lint:
	pylint azext_cdf
	
test-unit:
	python3 -m unittest discover -s tests/unit/ -p '*_test.py' -v

clean:
	rm -rf build
	rm -rf dist/
	rm -rf pytest_cache/
	rm -rf *.egg-info

clean-all: clean
	rm -rf $(VENV)
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f  {} +
	   
.PHONY: all source-venv
