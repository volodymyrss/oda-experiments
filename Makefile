IMAGE=admin.reproducible.online/oda-tests:$(shell git describe --always --dirty)
CONTAINER=odatests

run: build
	docker rm -f $(CONTAINER) || true
	docker run -p 8100:8000 -it --name $(CONTAINER) $(IMAGE) --rm

build:
	docker build -t $(IMAGE) .
