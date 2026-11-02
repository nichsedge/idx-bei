.PHONY: all build install test clean

all: build

build:
	@mkdir -p bin
	GOTOOLCHAIN=local go build -o bin/idx ./cmd/idx
	GOTOOLCHAIN=local go build -o bin/idx-server ./cmd/idx-server
	GOTOOLCHAIN=local go build -o bin/idx-sync ./cmd/idx-sync

build-arm64:
	@mkdir -p bin
	CGO_ENABLED=0 GOOS=android GOARCH=arm64 GOTOOLCHAIN=local go build -ldflags="-s -w" -o bin/idx ./cmd/idx
	CGO_ENABLED=0 GOOS=android GOARCH=arm64 GOTOOLCHAIN=local go build -ldflags="-s -w" -o bin/idx-server ./cmd/idx-server
	CGO_ENABLED=0 GOOS=android GOARCH=arm64 GOTOOLCHAIN=local go build -ldflags="-s -w" -o bin/idx-sync ./cmd/idx-sync

install: build
	GOTOOLCHAIN=local go install ./cmd/...
	@mkdir -p $(HOME)/.local/bin
	ln -sf $(HOME)/go/bin/idx $(HOME)/.local/bin/idx
	ln -sf $(HOME)/go/bin/idx-server $(HOME)/.local/bin/idx-server
	ln -sf $(HOME)/go/bin/idx-sync $(HOME)/.local/bin/idx-sync

test:
	GOTOOLCHAIN=local go test -v ./pkg/...

clean:
	rm -rf bin/
