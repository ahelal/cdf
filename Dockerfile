FROM mcr.microsoft.com/azure-cli
RUN apk add --update make && pip install --upgrade jinja2
RUN az bicep install
