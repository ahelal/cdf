# define the name of the virtual environment directory
VENV := venv
#
EXTENTION_NAME := cdf
# default target, when make executed without arguments
# all: source-venv

source-venv: $(VENV)/bin/activate
test: test-lint test-unit
venv:
	python3 -m venv $(VENV)
	pip3 install -r dev-requirements.txt

build: clean
	python3 setup.py bdist_wheel

uninstall: 
	az extension remove -n $(EXTENTION_NAME)&& echo "Removing installed extention!" || echo "Extention not installed ignoring!" 

install: build uninstall
	az extension add --upgrade -y --source ./dist/$(EXTENTION_NAME)*.whl

test-lint:
# stop the build if there are Python syntax errors or undefined names
	@echo "***** Running flake8 syntax  *****"
	flake8 azext_cdf --count --select=E9,F63,F7,F82 --show-source --statistics
	
# exit-zero treats all errors as warnings.
	@echo "***** Running flake8 warning *****"
	flake8 azext_cdf --count --exit-zero --max-complexity=10 --max-line-length=200 --statistics --exclude *_test.py

# pylint
	@echo "***** Running pylint *****"
	pylint azext_cdf

test-unit:
	# python3 -m unittest discover -s . -p '*_test.py' -v
	pytest -v

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
