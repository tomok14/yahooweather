#PYFILES := $(git ls-files '*.py' | grep -vE '^[a-zA-Z]\.py$$')
PYFILES := $(shell git ls-files '*.py')
CACHEDIR := ~/.cache/yahooweather
CONFIGDIR := ~/.config/yahooweather
SHAREDIR := ~/.local/share/yahooweather


lint:
	pylint $(PYFILES) | tee lintlog
	ruff check $(PYFILES) | tee rufflog

#install:
#	mkdir -p $(SHAREDIR)
#	cp location.db $(SHAREDIR)/location.db

install:
	python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps yahooweather-tomok14

upgrade:
	python3 -m pip install --index-url https://test.pypi.org/simple/ --no-deps --upgrade yahooweather-tomok14

list:
	python3 -m pip index versions yahooweather-tomok14 --index-url https://test.pypi.org/simple/

build:
	python3 -m build

upload:
	python3 -m twine upload --repository testpypi dist/*

clean:
	rm -rf dist build src/*.egg-info

purge_installed:
	# インストールしたファイル全消し
	rm -fr $(CACHEDIR) 
	rm -fr $(CONFIGDIR) 
	rm -fr $(SHAREDIR) 
