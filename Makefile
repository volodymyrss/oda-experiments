IMAGE=admin.reproducible.online/oda-tests:$(shell git describe --always)
CONTAINER=odatests

run: build
	docker rm -f $(CONTAINER) || true
	docker run \
                -p 8100:8000 \
                -it \
	        --rm \
	        -e ODATESTS_BOT_PASSWORD=$(shell cat testbot-password.txt) \
	        -e ODATESTS_SECRET_KEY=$(shell cat secret-key.txt) \
                --name $(CONTAINER) $(IMAGE)

build:
	docker build -t $(IMAGE) .

image-name: .FORCE
	echo $(IMAGE) > image-name

push: build
	docker push $(IMAGE)

.FORCE:
