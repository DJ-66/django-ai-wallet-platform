FROM rust:1.94.0-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       curl \
       ca-certificates \
       build-essential \
       pkg-config \
       libssl-dev \
       clang \
       cmake \
    && rm -rf /var/lib/apt/lists/*

# Builder-only Sui CLI.
# No wallet secret is installed in this image.
ARG SUI_REV=testnet-v1.71.1

RUN cargo install \
    --locked \
    --git https://github.com/MystenLabs/sui.git \
    --tag ${SUI_REV} \
    sui

COPY bin/sui-move /usr/local/bin/sui-move
RUN chmod 0755 /usr/local/bin/sui-move

WORKDIR /workspace

CMD ["bash"]
