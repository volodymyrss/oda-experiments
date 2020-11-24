REPO=admin.reproducible.online/oda-tests
IMAGE=$(REPO):$(shell git describe --always)
CONTAINER=odatests

run: build
	docker rm -f $(CONTAINER) || true
	docker run \
                -p 8100:8000 \
                -it \
	        --rm \
			    -e JENA_PASSWORD=$(shell cat ~/.jena-password ) \
					-e LOGSTASH_ENTRYPOINT=cdcihn:5001 \
	        -e ODATESTS_BOT_PASSWORD=$(shell cat testbot-password.txt) \
	        -e ODATESTS_SECRET_KEY=$(shell cat secret-key.txt) \
                --name $(CONTAINER) $(IMAGE)

build:
	docker build -t $(IMAGE) .

image-name: .FORCE
	echo $(IMAGE) > ../image-name

push: build
	docker push $(IMAGE)
	docker tag $(IMAGE) $(REPO):latest
	docker push $(REPO):latest

test:
	mypy *.py
	pylint -E  *.py

worker: build
	docker rm -f $(CONTAINER) || true
	docker run \
		-it \
		--rm \
		-e JENA_PASSWORD=$(shell cat ~/.jena-password ) \
		-e LOGSTASH_ENTRYPOINT=cdcihn:5001 \
		-e ODATESTS_BOT_PASSWORD=$(shell cat testbot-password.txt) \
		-e ODATESTS_SECRET_KEY=$(shell cat secret-key.txt) \
		--entrypoint python \
		--name $(CONTAINER) $(IMAGE) \
		/odaworker.py worker

.FORCE:
