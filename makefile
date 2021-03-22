# define the name of the virtual environment directory
VENV := venv
#
EXTENTION_NAME := cdf
# default target, when make executed without arguments
all: venv

venv: $(VENV)/bin/activate

install-venv:
	python3 -m venv $(VENV)
	pip3 install -r dev-requirements.txt

build: venv clean
	python3 setup.py bdist_wheel

uninstall: 
	az extension remove -n $(EXTENTION_NAME)&& echo "Removing installed extention!" || echo "Extention not installed ignoring!" 

install: build uninstall
	az extension add --upgrade -y --source ./dist/$(EXTENTION_NAME)*.whl

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
	   
.PHONY: all venv clean
