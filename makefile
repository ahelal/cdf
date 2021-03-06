# define the name of the virtual environment directory
VENV := venv
#
EXTENTION_NAME := cdf
# default target, when make executed without arguments
# all: source-venv

source-venv: $(VENV)/bin/activate
test: test-lint test-unit test-integration
test-integration: test-integration-code test-integration-bicep test-integration-terraform test-integration-arm

venv:
	python3 -m venv $(VENV)
	pip3 install -r dev-requirements.txt

build: clean
	python3 setup.py bdist_wheel

uninstall: 
	az extension remove -n $(EXTENTION_NAME)&& echo "Removing installed extention!" || echo "Extention not installed ignoring!" 

install: build uninstall
	az extension add --upgrade -y --source ./dist/$(EXTENTION_NAME)*.whl

docker-build:
	@echo "VERSION: $$(cat azext_cdf/version.py | grep VERSION | cut -d "=" -f2| xargs)"
	docker build -t cdf:$$(cat azext_cdf/version.py | grep VERSION | cut -d "=" -f2| xargs) .

docker-run:
	docker run -v $$(pwd):/cdf -it cdf:$$(cat azext_cdf/version.py | grep VERSION | cut -d "=" -f2| xargs)

test-lint:
# stop the build if there are Python syntax errors or undefined names
	@echo "***** Running flake8 syntax  *****"
	flake8 azext_cdf --count --select=E9,F63,F7,F82 --show-source --statistics
	
# exit-zero treats all errors as warnings.
	@echo "***** Running flake8 warning *****"
	flake8 azext_cdf --count --exit-zero --ignore=F405 --max-complexity=10 --max-line-length=200 --statistics --exclude *_test.py  

# pylint
	@echo "***** Running pylint *****"
	pylint --ignore-patterns=".*_test.py" azext_cdf

test-unit:
	# python3 -m unittest discover -s azext_cdf -p '*_test.py' -v
	pytest -v azext_cdf --color=yes --code-highlight=yes

test-integration-code:
	pytest -v tests --color=yes --code-highlight=yes -s

test-integration-arm:
	@echo "running expect default test"
	az cdf up -w ./tests/fixtures/arm/v2 
	az cdf status -w ./tests/fixtures/arm/v2 
	az cdf hook -w ./tests/fixtures/arm/v2 pass
	az cdf down -y -w ./tests/fixtures/arm/v2
	az cdf test -w ./tests/fixtures/arm/v2

test-integration-bicep:
	@echo "running expect default test"
	az cdf test -w ./tests/fixtures/bicep/v2 --down-strategy=always default
# also use cd instead of -w 
	@echo "running expect expect_to_fail_and_fails test"
	@cd ./tests/fixtures/bicep/v2 && az cdf test expect_to_fail_and_fails

test-integration-terraform:
	@echo "running expect terraform test"
	az cdf test -w ./tests/fixtures/terraform/v2/ --down-strategy=always

test-clean:
	find . -type d -iname foo -delete

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
