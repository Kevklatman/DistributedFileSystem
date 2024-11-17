FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY . .

RUN go mod tidy && \
    CGO_ENABLED=0 GOOS=linux go build -o /csi-driver cmd/main.go

FROM alpine:3.18

RUN apk add --no-cache ca-certificates

COPY --from=builder /csi-driver /bin/csi-driver

ENTRYPOINT ["/bin/csi-driver"]
