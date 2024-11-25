FROM golang:1.21-alpine AS builder

WORKDIR /app/storage-node
COPY storage-node/ .

RUN go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -o /storage-node cmd/main.go

FROM alpine:3.18

RUN apk add --no-cache ca-certificates && \
    mkdir -p /data && \
    chmod 750 /data

COPY --from=builder /storage-node /bin/storage-node

VOLUME ["/data"]
EXPOSE 8080

ENTRYPOINT ["/bin/storage-node"]
ENTRYPOINT ["/bin/storage-node"]
