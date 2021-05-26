FROM mcr.microsoft.com/azure-cli as builder
COPY . /cdf
RUN apk add --update make
RUN pip install --upgrade jinja2 & az bicep install
RUN cd /cdf; make build 

FROM mcr.microsoft.com/azure-cli
COPY --from=builder /cdf/dist/*whl /
RUN pip install --upgrade jinja2 && pip install --upgrade pytest && az bicep install
RUN az extension add --upgrade -y --source /*.whl && rm /*.whl
