import crypto from "node:crypto";
import fs from "node:fs";
import { DatabaseSync } from "node:sqlite";
import express, { NextFunction, Request, Response } from "express";
import { SuiGrpcClient } from "@mysten/sui/grpc";
import { Ed25519Keypair } from "@mysten/sui/keypairs/ed25519";
import { Transaction } from "@mysten/sui/transactions";

const PORT = Number(process.env.PORT || "3000");
const DB_PATH = process.env.FANZ_SUI_DB_PATH || "/data/fanz-sui.sqlite3";
const API_TOKEN = process.env.FANZ_SUI_API_TOKEN || "";
const SUI_MODE = process.env.FANZ_SUI_MODE || "mock";
const SUI_NETWORK = process.env.SUI_NETWORK || "testnet";
const SUI_GRPC_URL =
  process.env.SUI_GRPC_URL ||
  "https://fullnode.testnet.sui.io:443";

const TESTNET_PREPARE_ENABLED =
  process.env.FANZ_SUI_TESTNET_PREPARE_ENABLED === "true";

const TESTNET_SUBMIT_ENABLED =
  process.env.FANZ_SUI_TESTNET_SUBMIT_ENABLED === "true";

const TESTNET_PUBLICATION_SUBMIT_ENABLED =
  process.env.FANZ_SUI_TESTNET_PUBLICATION_SUBMIT_ENABLED === "true";

const MAINNET_PUBLICATION_PREPARE_ENABLED =
  process.env.FANZ_SUI_MAINNET_PUBLICATION_PREPARE_ENABLED === "true";

const MAINNET_PUBLICATION_SUBMIT_ENABLED =
  process.env.FANZ_SUI_MAINNET_PUBLICATION_SUBMIT_ENABLED === "true";

const TESTNET_CURRENCY_REGISTRATION_ENABLED =
  process.env.FANZ_SUI_TESTNET_CURRENCY_REGISTRATION_ENABLED === "true";

const MAINNET_CURRENCY_REGISTRATION_ENABLED =
  process.env.FANZ_SUI_MAINNET_CURRENCY_REGISTRATION_ENABLED === "true";

const MAINNET_TRANSFER_ENABLED =
  process.env.FANZ_SUI_MAINNET_TRANSFER_ENABLED === "true";

const MAINNET_STARTER_GRANT_ENABLED =
  process.env.FANZ_SUI_MAINNET_STARTER_GRANT_ENABLED === "true";

const MAINNET_STARTER_GRANT_MIST =
  250_000_000n;

const MAINNET_TREASURY_ADDRESS =
  (
    process.env.FANZ_SUI_MAINNET_TREASURY_ADDRESS ||
    ""
  ).trim().toLowerCase();

const MAINNET_SWEEP_FLOOR_MIST =
  10_000_000_000n;

const MAINNET_SWEEP_EXCESS_BPS =
  8000n;

const SUI_USD_PRICE_URL =
  process.env.FANZ_SUI_USD_PRICE_URL ||
  "https://api.coingecko.com/api/v3/simple/price"
  + "?ids=sui&vs_currencies=usd";

const SUI_PRICE_CACHE_MS =
  Number(
    process.env.FANZ_SUI_PRICE_CACHE_MS ||
    "60000"
  );

const SUI_QUOTE_TTL_MS =
  Number(
    process.env.FANZ_SUI_QUOTE_TTL_MS ||
    "900000"
  );

let cachedSuiUsdPrice: {
  price: number;
  fetchedAt: number;
} | null = null;


async function getSuiUsdPrice(): Promise<number> {
  const now = Date.now();

  if (
    cachedSuiUsdPrice &&
    (
      now - cachedSuiUsdPrice.fetchedAt
      < SUI_PRICE_CACHE_MS
    )
  ) {
    return cachedSuiUsdPrice.price;
  }

  const response = await fetch(
    SUI_USD_PRICE_URL,
    {
      headers: {
        Accept: "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error(
      `SUI price source returned HTTP `
      + `${response.status}`
    );
  }

  const body =
    await response.json() as {
      sui?: {
        usd?: number;
      };
    };

  const price = Number(
    body?.sui?.usd
  );

  if (
    !Number.isFinite(price) ||
    price <= 0
  ) {
    throw new Error(
      "SUI price source returned invalid price"
    );
  }

  cachedSuiUsdPrice = {
    price,
    fetchedAt: now,
  };

  return price;
}


async function quoteMainnetSuiPayment(
  amountUsd: number,
) {
  if (
    !Number.isFinite(amountUsd) ||
    amountUsd <= 0
  ) {
    throw new Error(
      "amount_usd must be greater than zero"
    );
  }

  const hotAddress = (
    process.env
      .FANZ_SUI_MAINNET_HOT_ADDRESS ||
    ""
  )
    .trim()
    .toLowerCase();

  if (
    !/^0x[0-9a-f]{64}$/.test(
      hotAddress
    )
  ) {
    throw new Error(
      "FANZ mainnet Sui hot address "
      + "is not configured"
    );
  }

  const suiUsd =
    await getSuiUsdPrice();

  const amountSui =
    amountUsd / suiUsd;

  const amountMist =
    BigInt(
      Math.ceil(
        amountSui * 1_000_000_000
      )
    );

  const now = Date.now();

  return {
    network: "mainnet",
    recipient_address: hotAddress,
    amount_usd:
      amountUsd.toFixed(2),
    sui_usd_price:
      suiUsd.toString(),
    amount_mist:
      amountMist.toString(),
    amount_sui:
      (
        `${amountMist / 1_000_000_000n}.`
        + `${amountMist % 1_000_000_000n}`
          .padStart(9, "0")
      ),
    quoted_at:
      new Date(now).toISOString(),
    quote_expires_at:
      new Date(
        now + SUI_QUOTE_TTL_MS
      ).toISOString(),
  };
}



if (!API_TOKEN) {
  throw new Error("FANZ_SUI_API_TOKEN is required");
}

fs.mkdirSync(new URL(".", `file://${DB_PATH}`).pathname, {
  recursive: true,
});

const db = new DatabaseSync(DB_PATH);

db.exec(`
  PRAGMA journal_mode = WAL;

  CREATE TABLE IF NOT EXISTS deliveries (
    submission_key TEXT PRIMARY KEY,
    chain TEXT NOT NULL,
    coin_type TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    amount_base_units TEXT NOT NULL,
    state TEXT NOT NULL,
    sender_address TEXT,
    transaction_bytes_b64 TEXT,
    signature TEXT,
    tx_digest TEXT UNIQUE,
    prepared_at TEXT,
    submitted_at TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS mainnet_transfers (
    submission_key TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    recipient_address TEXT NOT NULL,
    amount_mist TEXT NOT NULL,
    state TEXT NOT NULL,
    sender_address TEXT,
    tx_digest TEXT UNIQUE,
    submitted_at TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
`);


function ensureColumn(
  table: string,
  column: string,
  definition: string,
): void {
  const columns = db.prepare(
    `PRAGMA table_info(${table})`
  ).all() as Array<{ name: string }>;

  if (!columns.some((item) => item.name === column)) {
    db.exec(
      `ALTER TABLE ${table} ADD COLUMN ${column} ${definition}`
    );
  }
}

// Durable schema upgrades for journals created by earlier fanz-sui versions.
ensureColumn(
  "deliveries",
  "transaction_bytes_b64",
  "TEXT",
);
ensureColumn(
  "deliveries",
  "signature",
  "TEXT",
);
ensureColumn(
  "deliveries",
  "prepared_at",
  "TEXT",
);
ensureColumn(
  "deliveries",
  "submitted_at",
  "TEXT",
);
ensureColumn(
  "deliveries",
  "confirmed_at",
  "TEXT",
);

db.exec(`
  UPDATE deliveries
  SET prepared_at = updated_at
  WHERE state = 'prepared'
    AND prepared_at IS NULL;
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS creator_publications (
    publication_key TEXT PRIMARY KEY,
    chain TEXT NOT NULL,
    recipient_address TEXT,
    module_name TEXT NOT NULL,
    coin_struct_name TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    modules_json TEXT NOT NULL,
    dependency_ids_json TEXT NOT NULL,
    state TEXT NOT NULL,
    sender_address TEXT,
    transaction_bytes_b64 TEXT,
    signature TEXT,
    tx_digest TEXT UNIQUE,
    package_id TEXT,
    coin_type TEXT,
    metadata_cap_object_id TEXT,
    registration_tx_digest TEXT,
    registered_currency_object_id TEXT,
    registered_at TEXT,
    coin_image_url TEXT,
    coin_image_tx_digest TEXT,
    coin_image_set_at TEXT,
    coin_image_change_count INTEGER NOT NULL DEFAULT 0,
    prepared_at TEXT,
    submitted_at TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
`);

ensureColumn(
  "creator_publications",
  "recipient_address",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "network",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "metadata_cap_object_id",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "registration_tx_digest",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "registered_currency_object_id",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "registered_at",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "coin_image_url",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "coin_image_tx_digest",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "coin_image_set_at",
  "TEXT",
);

ensureColumn(
  "creator_publications",
  "coin_image_change_count",
  "INTEGER NOT NULL DEFAULT 0",
);

type MainnetTransferRow = {
  submission_key: string;
  purpose: string;
  recipient_address: string;
  amount_mist: string;
  state: string;
  sender_address: string | null;
  tx_digest: string | null;
  submitted_at: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};


function getMainnetTransfer(
  submissionKey: string,
): MainnetTransferRow | undefined {
  return db.prepare(`
    SELECT
      submission_key,
      purpose,
      recipient_address,
      amount_mist,
      state,
      sender_address,
      tx_digest,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    FROM mainnet_transfers
    WHERE submission_key = ?
  `).get(submissionKey) as
    | MainnetTransferRow
    | undefined;
}


function publicMainnetTransfer(
  row: MainnetTransferRow,
) {
  return {
    submission_key: row.submission_key,
    purpose: row.purpose,
    recipient_address: row.recipient_address,
    amount_mist: row.amount_mist,
    state: row.state,
    sender_address: row.sender_address,
    tx_digest: row.tx_digest,
    submitted_at: row.submitted_at,
    confirmed_at: row.confirmed_at,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}


function calculateMainnetTreasurySweep(
  balanceMist: bigint,
): bigint {
  if (
    balanceMist <= MAINNET_SWEEP_FLOOR_MIST
  ) {
    return 0n;
  }

  const excess =
    balanceMist - MAINNET_SWEEP_FLOOR_MIST;

  return (
    excess
    * MAINNET_SWEEP_EXCESS_BPS
    / 10_000n
  );
}


type DeliveryInput = {
  submission_key: string;
  chain: string;
  coin_type: string;
  recipient_address: string;
  amount_base_units: string;
};

type DeliveryRow = DeliveryInput & {
  state: string;
  sender_address: string | null;
  transaction_bytes_b64: string | null;
  signature: string | null;
  tx_digest: string | null;
  prepared_at: string | null;
  submitted_at: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

type CreatorPublicationInput = {
  publication_key: string;
  chain: string;
  network: string;
  recipient_address: string;
  module_name: string;
  coin_struct_name: string;
  source_sha256: string;
  artifact_sha256: string;
  modules: string[];
  dependency_ids: string[];
};

type CreatorPublicationRow = {
  publication_key: string;
  chain: string;
  network: string | null;
  recipient_address: string | null;
  module_name: string;
  coin_struct_name: string;
  source_sha256: string;
  artifact_sha256: string;
  modules_json: string;
  dependency_ids_json: string;
  state: string;
  sender_address: string | null;
  transaction_bytes_b64: string | null;
  signature: string | null;
  tx_digest: string | null;
  package_id: string | null;
  coin_type: string | null;
  metadata_cap_object_id: string | null;
  registration_tx_digest: string | null;
  registered_currency_object_id: string | null;
  registered_at: string | null;
  coin_image_url: string | null;
  coin_image_tx_digest: string | null;
  coin_image_set_at: string | null;
  coin_image_change_count: number;
  prepared_at: string | null;
  submitted_at: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

function constantTimeTokenMatch(provided: string): boolean {
  const expected = Buffer.from(API_TOKEN);
  const actual = Buffer.from(provided);

  if (expected.length !== actual.length) {
    return false;
  }

  return crypto.timingSafeEqual(expected, actual);
}

function authenticate(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  const header = req.header("authorization") || "";
  const prefix = "Bearer ";

  if (
    !header.startsWith(prefix) ||
    !constantTimeTokenMatch(header.slice(prefix.length))
  ) {
    res.status(401).json({ error: "unauthorized" });
    return;
  }

  next();
}

function validateDelivery(body: unknown): DeliveryInput {
  if (!body || typeof body !== "object") {
    throw new Error("request body must be an object");
  }

  const value = body as Record<string, unknown>;

  const required = [
    "submission_key",
    "chain",
    "coin_type",
    "recipient_address",
    "amount_base_units",
  ] as const;

  for (const key of required) {
    if (
      typeof value[key] !== "string" ||
      value[key].trim() === ""
    ) {
      throw new Error(`${key} must be a non-empty string`);
    }
  }

  if (!/^[0-9]+$/.test(value.amount_base_units as string)) {
    throw new Error("amount_base_units must be a positive integer string");
  }

  if (BigInt(value.amount_base_units as string) <= 0n) {
    throw new Error("amount_base_units must be positive");
  }

  return {
    submission_key: value.submission_key as string,
    chain: value.chain as string,
    coin_type: value.coin_type as string,
    recipient_address: value.recipient_address as string,
    amount_base_units: value.amount_base_units as string,
  };
}

function validateCreatorPublication(
  body: unknown,
): CreatorPublicationInput {
  if (!body || typeof body !== "object") {
    throw new Error("request body must be an object");
  }

  const value = body as Record<string, unknown>;

  const requiredStrings = [
    "publication_key",
    "chain",
    "network",
    "recipient_address",
    "module_name",
    "coin_struct_name",
    "source_sha256",
    "artifact_sha256",
  ] as const;

  for (const key of requiredStrings) {
    if (
      typeof value[key] !== "string" ||
      value[key].trim() === ""
    ) {
      throw new Error(`${key} must be a non-empty string`);
    }
  }

  if (value.chain !== "sui") {
    throw new Error("chain must be sui");
  }

  if (
    value.network !== "testnet" &&
    value.network !== "mainnet"
  ) {
    throw new Error(
      "network must be testnet or mainnet"
    );
  }

  if (
    !/^0x[0-9a-f]{64}$/.test(
      value.recipient_address as string,
    )
  ) {
    throw new Error(
      "recipient_address must be a canonical lowercase Sui address"
    );
  }

  if (
    !/^[a-z][a-z0-9_]*$/.test(
      value.module_name as string,
    )
  ) {
    throw new Error("module_name is invalid");
  }

  if (
    !/^[A-Z][A-Z0-9_]*$/.test(
      value.coin_struct_name as string,
    )
  ) {
    throw new Error("coin_struct_name is invalid");
  }

  for (const key of ["source_sha256", "artifact_sha256"] as const) {
    if (
      !/^[0-9a-f]{64}$/.test(
        value[key] as string,
      )
    ) {
      throw new Error(`${key} must be lowercase SHA-256 hex`);
    }
  }

  if (
    !Array.isArray(value.modules) ||
    value.modules.length === 0 ||
    !value.modules.every(
      (item) =>
        typeof item === "string" &&
        item.length > 0 &&
        /^[A-Za-z0-9+/]+={0,2}$/.test(item) &&
        item.length % 4 === 0 &&
        Buffer.from(item, "base64").toString("base64") === item,
    )
  ) {
    throw new Error(
      "modules must be a non-empty array of canonical base64 strings"
    );
  }

  if (
    !Array.isArray(value.dependency_ids) ||
    !value.dependency_ids.every(
      (item) => {
        if (typeof item !== "string") {
          return false;
        }

        if (!/^0x[0-9a-fA-F]{1,64}$/.test(item)) {
          return false;
        }

        try {
          BigInt(item);
          return true;
        } catch {
          return false;
        }
      },
    )
  ) {
    throw new Error(
      "dependency_ids must be an array of Sui package IDs"
    );
  }

  return {
    publication_key: value.publication_key as string,
    chain: value.chain as string,
    network: value.network as string,
    recipient_address: value.recipient_address as string,
    module_name: value.module_name as string,
    coin_struct_name: value.coin_struct_name as string,
    source_sha256: value.source_sha256 as string,
    artifact_sha256: value.artifact_sha256 as string,
    modules: value.modules as string[],
    dependency_ids: value.dependency_ids as string[],
  };
}


function getCreatorPublication(
  publicationKey: string,
): CreatorPublicationRow | undefined {
  return db.prepare(`
    SELECT
      publication_key,
      chain,
      network,
      recipient_address,
      module_name,
      coin_struct_name,
      source_sha256,
      artifact_sha256,
      modules_json,
      dependency_ids_json,
      state,
      sender_address,
      transaction_bytes_b64,
      signature,
      tx_digest,
      package_id,
      coin_type,
      metadata_cap_object_id,
      registration_tx_digest,
      registered_currency_object_id,
      registered_at,
      coin_image_url,
      coin_image_tx_digest,
      coin_image_set_at,
      coin_image_change_count,
      prepared_at,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    FROM creator_publications
    WHERE publication_key = ?
  `).get(publicationKey) as
    | CreatorPublicationRow
    | undefined;
}


function creatorPublicationImmutableFieldsMatch(
  existing: CreatorPublicationRow,
  requested: CreatorPublicationInput,
): boolean {
  return (
    existing.chain === requested.chain &&
    existing.network === requested.network &&
    existing.recipient_address === requested.recipient_address &&
    existing.module_name === requested.module_name &&
    existing.coin_struct_name === requested.coin_struct_name &&
    existing.source_sha256 === requested.source_sha256 &&
    existing.artifact_sha256 === requested.artifact_sha256 &&
    existing.modules_json === JSON.stringify(requested.modules) &&
    existing.dependency_ids_json ===
      JSON.stringify(requested.dependency_ids)
  );
}


function publicCreatorPublication(
  row: CreatorPublicationRow,
) {
  return {
    publication_key: row.publication_key,
    chain: row.chain,
    network: row.network,
    recipient_address: row.recipient_address,
    module_name: row.module_name,
    coin_struct_name: row.coin_struct_name,
    source_sha256: row.source_sha256,
    artifact_sha256: row.artifact_sha256,
    state: row.state,
    sender_address: row.sender_address,
    tx_digest: row.tx_digest,
    package_id: row.package_id,
    coin_type: row.coin_type,
    metadata_cap_object_id:
      row.metadata_cap_object_id,
    registration_tx_digest:
      row.registration_tx_digest,
    registered_currency_object_id:
      row.registered_currency_object_id,
    registered_at: row.registered_at,
    coin_image_url: row.coin_image_url,
    coin_image_tx_digest:
      row.coin_image_tx_digest,
    coin_image_set_at:
      row.coin_image_set_at,
    coin_image_change_count:
      row.coin_image_change_count,
    coin_image_next_price_usd:
      row.coin_image_change_count === 0
        ? "0.00"
        : "5.00",
    prepared_at: row.prepared_at,
    submitted_at: row.submitted_at,
    confirmed_at: row.confirmed_at,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}


function getDelivery(submissionKey: string): DeliveryRow | undefined {
  return db.prepare(`
    SELECT
      submission_key,
      chain,
      coin_type,
      recipient_address,
      amount_base_units,
      state,
      sender_address,
      transaction_bytes_b64,
      signature,
      tx_digest,
      prepared_at,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    FROM deliveries
    WHERE submission_key = ?
  `).get(submissionKey) as DeliveryRow | undefined;
}

function immutableFieldsMatch(
  existing: DeliveryRow,
  requested: DeliveryInput,
): boolean {
  return (
    existing.chain === requested.chain &&
    existing.coin_type === requested.coin_type &&
    existing.recipient_address === requested.recipient_address &&
    existing.amount_base_units === requested.amount_base_units
  );
}


function publicDelivery(row: DeliveryRow) {
  return {
    submission_key: row.submission_key,
    chain: row.chain,
    coin_type: row.coin_type,
    recipient_address: row.recipient_address,
    amount_base_units: row.amount_base_units,
    state: row.state,
    sender_address: row.sender_address,
    tx_digest: row.tx_digest,
    prepared_at: row.prepared_at,
    submitted_at: row.submitted_at,
    confirmed_at: row.confirmed_at,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

async function prepareCreatorPublication(
  publicationKey: string,
): Promise<CreatorPublicationRow> {
  const existing =
    getCreatorPublication(publicationKey);

  if (!existing) {
    throw new Error(
      "Creator publication not found"
    );
  }

  if (
    existing.transaction_bytes_b64 &&
    existing.signature
  ) {
    // Critical invariant:
    // once signed publication material exists,
    // NEVER rebuild it.
    return existing;
  }

  if (existing.tx_digest) {
    throw new Error(
      "Creator publication already has a transaction digest"
    );
  }

  if (
    existing.state !== "accepted" &&
    existing.state !== "prepared"
  ) {
    throw new Error(
      `Cannot prepare creator publication in state ${existing.state}`
    );
  }

  const keypair =
    requireCreatorPublicationSigner(
      existing.network
    );

  const sender = keypair.toSuiAddress();

  const modules =
    JSON.parse(existing.modules_json) as string[];

  const dependencies =
    JSON.parse(
      existing.dependency_ids_json
    ) as string[];

  if (
    !Array.isArray(modules) ||
    modules.length === 0 ||
    !modules.every(
      (item) =>
        typeof item === "string" &&
        item.length > 0,
    )
  ) {
    throw new Error(
      "Journaled publication modules are invalid"
    );
  }

  if (
    !Array.isArray(dependencies) ||
    !dependencies.every(
      (item) => typeof item === "string",
    )
  ) {
    throw new Error(
      "Journaled publication dependencies are invalid"
    );
  }

  const preparingAt =
    new Date().toISOString();

    const claim = db.prepare(`
    UPDATE creator_publications
    SET
      state = 'preparing',
      sender_address = ?,
      updated_at = ?
    WHERE publication_key = ?
      AND state = 'accepted'
      AND tx_digest IS NULL
      AND transaction_bytes_b64 IS NULL
      AND signature IS NULL
  `).run(
    sender,
    preparingAt,
    publicationKey,
  );

  if (claim.changes !== 1) {
    const current =
      getCreatorPublication(publicationKey);

    if (
      current?.transaction_bytes_b64 &&
      current?.signature
    ) {
      return current;
    }

    if (current?.state === "preparing") {
      throw new Error(
        "Creator publication preparation is already in progress"
      );
    }

    throw new Error(
      "Creator publication could not be claimed for preparation"
    );
  }

  const tx = new Transaction();

  tx.setSender(sender);

  const [upgradeCap] = tx.publish({
    modules,
    dependencies,
  });

  if (!existing.recipient_address) {
    throw new Error(
      "Creator publication has no recipient address"
    );
  }

  tx.transferObjects(
    [upgradeCap],
    existing.recipient_address,
  );

  const client =
    creatorPublicationClient(
      existing.network
    );

  const bytes = await tx.build({
    client,
  });

  const signed =
    await keypair.signTransaction(bytes);

  const bytesB64 =
    Buffer.from(bytes).toString("base64");

  const preparedAt =
    new Date().toISOString();

  const update = db.prepare(`
    UPDATE creator_publications
    SET
      state = 'prepared',
      sender_address = ?,
      transaction_bytes_b64 = ?,
      signature = ?,
      prepared_at = ?,
      updated_at = ?
    WHERE publication_key = ?
      AND tx_digest IS NULL
      AND transaction_bytes_b64 IS NULL
      AND signature IS NULL
  `).run(
    sender,
    bytesB64,
    signed.signature,
    preparedAt,
    preparedAt,
    publicationKey,
  );

  if (update.changes !== 1) {
    const raced =
      getCreatorPublication(publicationKey);

    if (
      raced?.transaction_bytes_b64 &&
      raced?.signature
    ) {
      return raced;
    }

    throw new Error(
      "Prepared creator publication journal update failed"
    );
  }

  const prepared =
    getCreatorPublication(publicationKey);

  if (!prepared) {
    throw new Error(
      "Prepared creator publication disappeared from journal"
    );
  }

  return prepared;
}

async function submitPreparedCreatorPublication(
  publicationKey: string,
): Promise<CreatorPublicationRow> {
  const row =
    getCreatorPublication(publicationKey);

  if (!row) {
    throw new Error(
      "Creator publication not found"
    );
  }

  requireCreatorPublicationSubmitEnabled(
    row.network
  );

  if (row.tx_digest) {
    // Once the chain returns an authoritative digest,
    // NEVER execute these bytes again.
    return row;
  }

  if (row.state !== "prepared") {
    throw new Error(
      `Expected prepared state; found ${row.state}`
    );
  }

  if (
    !row.transaction_bytes_b64 ||
    !row.signature
  ) {
    throw new Error(
      "Prepared creator publication material is missing"
    );
  }

  const bytes = Buffer.from(
    row.transaction_bytes_b64,
    "base64",
  );

  const result =
    await creatorPublicationClient(
      row.network
    ).executeTransaction({
      transaction: bytes,
      signatures: [row.signature],
      include: {
        effects: true,
        balanceChanges: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Sui publication execution returned no transaction"
    );
  }

  const now = new Date().toISOString();

  const success =
    transaction.status.success === true;

  const state =
    success ? "submitted" : "failed";

  const update = db.prepare(`
    UPDATE creator_publications
    SET
      state = ?,
      tx_digest = ?,
      submitted_at = ?,
      updated_at = ?
    WHERE publication_key = ?
      AND tx_digest IS NULL
  `).run(
    state,
    transaction.digest,
    now,
    now,
    publicationKey,
  );

  if (update.changes !== 1) {
    const raced =
      getCreatorPublication(publicationKey);

    if (raced?.tx_digest) {
      return raced;
    }

    throw new Error(
      "Creator publication submission journal update failed"
    );
  }

  const updated =
    getCreatorPublication(publicationKey);

  if (!updated) {
    throw new Error(
      "Submitted creator publication disappeared from journal"
    );
  }

  return updated;
}

function requireTestnetSigner(): Ed25519Keypair {
  if (SUI_NETWORK !== "testnet") {
    throw new Error(
      "Testnet lifecycle requires SUI_NETWORK=testnet"
    );
  }

  const secret =
    process.env.FANZ_SUI_TESTNET_PRIVATE_KEY || "";

  if (!secret) {
    throw new Error(
      "FANZ_SUI_TESTNET_PRIVATE_KEY is missing"
    );
  }

  return Ed25519Keypair.fromSecretKey(secret);
}


function testnetClient(): SuiGrpcClient {
  return new SuiGrpcClient({
    network: "testnet",
    baseUrl: SUI_GRPC_URL,
  });
}


function loadMainnetSigner(): Ed25519Keypair {
  const walletPath =
    process.env.FANZ_SUI_MAINNET_WALLET_PATH ||
    "";

  if (!walletPath) {
    throw new Error(
      "FANZ_SUI_MAINNET_WALLET_PATH is missing"
    );
  }

  const wallet = JSON.parse(
    fs.readFileSync(walletPath, "utf8")
  ) as {
    network?: string;
    address?: string;
    private_key?: string;
  };

  if (
    wallet.network !== "mainnet" ||
    !wallet.private_key ||
    !wallet.address
  ) {
    throw new Error(
      "Mainnet wallet file is invalid"
    );
  }

  const keypair =
    Ed25519Keypair.fromSecretKey(
      wallet.private_key
    );

  const derived =
    keypair.toSuiAddress().toLowerCase();

  if (
    derived !== wallet.address.toLowerCase()
  ) {
    throw new Error(
      "Mainnet wallet key/address mismatch"
    );
  }

  const configuredHot =
    (
      process.env.FANZ_SUI_MAINNET_HOT_ADDRESS ||
      ""
    ).trim().toLowerCase();

  if (
    configuredHot &&
    derived !== configuredHot
  ) {
    throw new Error(
      "Mainnet signer does not match configured hot wallet"
    );
  }

  return keypair;
}


function requireMainnetSigner(): Ed25519Keypair {
  if (!MAINNET_TRANSFER_ENABLED) {
    throw new Error(
      "Mainnet Sui transfers are disabled"
    );
  }

  return loadMainnetSigner();
}


function requireCreatorCurrencyRegistrationSigner(
  network: string | null,
): Ed25519Keypair {
  requireCreatorCurrencyRegistrationEnabled(
    network
  );

  if (network === "testnet") {
    return requireTestnetSigner();
  }

  if (network === "mainnet") {
    return loadMainnetSigner();
  }

  throw new Error(
    "Creator publication has no valid network"
  );
}


function mainnetClient(): SuiGrpcClient {
  return new SuiGrpcClient({
    network: "mainnet",
    baseUrl:
      process.env.SUI_MAINNET_GRPC_URL ||
      "https://fullnode.mainnet.sui.io:443",
  });
}


function creatorPublicationClient(
  network: string | null,
): SuiGrpcClient {
  if (network === "testnet") {
    return testnetClient();
  }

  if (network === "mainnet") {
    return mainnetClient();
  }

  throw new Error(
    "Creator publication has no valid network"
  );
}


function requireCreatorPublicationSigner(
  network: string | null,
): Ed25519Keypair {
  if (network === "testnet") {
    if (!TESTNET_PREPARE_ENABLED) {
      throw new Error(
        "Testnet transaction preparation is disabled"
      );
    }

    return requireTestnetSigner();
  }

  if (network === "mainnet") {
    if (!MAINNET_PUBLICATION_PREPARE_ENABLED) {
      throw new Error(
        "Mainnet creator publication preparation is disabled"
      );
    }

    return requireMainnetSigner();
  }

  throw new Error(
    "Creator publication has no valid network"
  );
}


function requireCreatorCurrencyRegistrationEnabled(
  network: string | null,
): void {
  if (network === "testnet") {
    if (!TESTNET_CURRENCY_REGISTRATION_ENABLED) {
      throw new Error(
        "Testnet creator Currency registration is disabled"
      );
    }

    return;
  }

  if (network === "mainnet") {
    if (!MAINNET_CURRENCY_REGISTRATION_ENABLED) {
      throw new Error(
        "Mainnet creator Currency registration is disabled"
      );
    }

    return;
  }

  throw new Error(
    "Creator publication has no valid network"
  );
}


function requireCreatorPublicationSubmitEnabled(
  network: string | null,
): void {
  if (network === "testnet") {
    if (!TESTNET_PUBLICATION_SUBMIT_ENABLED) {
      throw new Error(
        "Testnet creator publication submission is disabled"
      );
    }

    return;
  }

  if (network === "mainnet") {
    if (!MAINNET_PUBLICATION_SUBMIT_ENABLED) {
      throw new Error(
        "Mainnet creator publication submission is disabled"
      );
    }

    return;
  }

  throw new Error(
    "Creator publication has no valid network"
  );
}


type SuiPaymentVerificationInput = {
  tx_digest: string;
  recipient_address: string;
  minimum_amount_mist: string;
};


function validateSuiPaymentVerification(
  input: unknown,
): SuiPaymentVerificationInput {
  if (
    !input ||
    typeof input !== "object"
  ) {
    throw new Error(
      "Payment verification payload must be an object"
    );
  }

  const value = input as Record<string, unknown>;

  const txDigest =
    String(value.tx_digest || "").trim();

  const recipientAddress =
    String(value.recipient_address || "")
      .trim()
      .toLowerCase();

  const minimumAmountMist =
    String(value.minimum_amount_mist || "")
      .trim();

  if (!txDigest) {
    throw new Error(
      "tx_digest is required"
    );
  }

  if (
    !/^0x[0-9a-f]{64}$/.test(
      recipientAddress
    )
  ) {
    throw new Error(
      "recipient_address must be a valid Sui address"
    );
  }

  if (
    !/^[0-9]+$/.test(
      minimumAmountMist
    )
  ) {
    throw new Error(
      "minimum_amount_mist must be a positive integer"
    );
  }

  if (
    BigInt(minimumAmountMist) <= 0n
  ) {
    throw new Error(
      "minimum_amount_mist must be greater than zero"
    );
  }

  return {
    tx_digest: txDigest,
    recipient_address: recipientAddress,
    minimum_amount_mist: minimumAmountMist,
  };
}


async function executeMainnetStarterGrant({
  submissionKey,
  recipientAddress,
}: {
  submissionKey: string;
  recipientAddress: string;
}): Promise<MainnetTransferRow> {
  if (!MAINNET_STARTER_GRANT_ENABLED) {
    throw new Error(
      "Mainnet Sui starter grants are disabled"
    );
  }

  const recipient =
    recipientAddress
      .trim()
      .toLowerCase();

  if (
    !/^0x[0-9a-f]{64}$/.test(recipient)
  ) {
    throw new Error(
      "Starter grant recipient is not "
      + "a valid Sui address"
    );
  }

  const key =
    submissionKey.trim();

  if (
    !/^[A-Za-z0-9._:-]{1,160}$/.test(key)
  ) {
    throw new Error(
      "Starter grant submission_key is invalid"
    );
  }

  const purpose =
    "starter_grant";

  const amountMist =
    MAINNET_STARTER_GRANT_MIST;

  const existing =
    getMainnetTransfer(key);

  if (existing) {
    if (
      existing.purpose !== purpose ||
      existing.recipient_address !== recipient ||
      existing.amount_mist !==
        amountMist.toString()
    ) {
      throw new Error(
        "submission_key already exists "
        + "with different starter grant terms"
      );
    }

    return existing;
  }

  const keypair =
    requireMainnetSigner();

  const sender =
    keypair
      .toSuiAddress()
      .toLowerCase();

  if (sender === recipient) {
    throw new Error(
      "Starter grant recipient cannot "
      + "be the FANZ hot wallet"
    );
  }

  const now =
    new Date().toISOString();

  db.prepare(`
    INSERT INTO mainnet_transfers (
      submission_key,
      purpose,
      recipient_address,
      amount_mist,
      state,
      sender_address,
      tx_digest,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    )
    VALUES (
      ?, ?, ?, ?, 'accepted', ?,
      NULL, NULL, NULL, ?, ?
    )
  `).run(
    key,
    purpose,
    recipient,
    amountMist.toString(),
    sender,
    now,
    now,
  );

  const client =
    mainnetClient();

  const tx =
    new Transaction();

  const [grantCoin] =
    tx.splitCoins(
      tx.gas,
      [amountMist],
    );

  tx.transferObjects(
    [grantCoin],
    recipient,
  );

  const result =
    await client.signAndExecuteTransaction({
      signer: keypair,
      transaction: tx,
      include: {
        effects: true,
        balanceChanges: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Starter grant returned "
      + "no Sui transaction"
    );
  }

  const success =
    transaction.status.success === true;

  const finished =
    new Date().toISOString();

  db.prepare(`
    UPDATE mainnet_transfers
    SET
      state = ?,
      tx_digest = ?,
      submitted_at = ?,
      confirmed_at = ?,
      updated_at = ?
    WHERE submission_key = ?
      AND tx_digest IS NULL
  `).run(
    success ? "confirmed" : "failed",
    transaction.digest,
    finished,
    success ? finished : null,
    finished,
    key,
  );

  const updated =
    getMainnetTransfer(key);

  if (!updated) {
    throw new Error(
      "Starter grant journal disappeared"
    );
  }

  return updated;
}


async function executeMainnetTreasuryTransfer({
  submissionKey,
  purpose,
  amountMist,
}: {
  submissionKey: string;
  purpose: string;
  amountMist: bigint;
}): Promise<MainnetTransferRow> {
  if (
    !/^0x[0-9a-f]{64}$/.test(
      MAINNET_TREASURY_ADDRESS
    )
  ) {
    throw new Error(
      "Mainnet treasury address is not configured"
    );
  }

  if (amountMist <= 0n) {
    throw new Error(
      "Mainnet transfer amount must be positive"
    );
  }

  const existing =
    getMainnetTransfer(submissionKey);

  if (existing) {
    if (
      existing.purpose !== purpose ||
      existing.recipient_address !==
        MAINNET_TREASURY_ADDRESS ||
      existing.amount_mist !==
        amountMist.toString()
    ) {
      throw new Error(
        "submission_key already exists "
        + "with different transfer terms"
      );
    }

    return existing;
  }

  const keypair = requireMainnetSigner();
  const sender =
    keypair.toSuiAddress().toLowerCase();

  const now = new Date().toISOString();

  db.prepare(`
    INSERT INTO mainnet_transfers (
      submission_key,
      purpose,
      recipient_address,
      amount_mist,
      state,
      sender_address,
      tx_digest,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    )
    VALUES (
      ?, ?, ?, ?, 'accepted', ?,
      NULL, NULL, NULL, ?, ?
    )
  `).run(
    submissionKey,
    purpose,
    MAINNET_TREASURY_ADDRESS,
    amountMist.toString(),
    sender,
    now,
    now,
  );

  const client = mainnetClient();
  const tx = new Transaction();

  const [paymentCoin] =
    tx.splitCoins(
      tx.gas,
      [amountMist],
    );

  tx.transferObjects(
    [paymentCoin],
    MAINNET_TREASURY_ADDRESS,
  );

  const result =
    await client.signAndExecuteTransaction({
      signer: keypair,
      transaction: tx,
      include: {
        effects: true,
        balanceChanges: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Mainnet Sui transfer returned "
      + "no transaction"
    );
  }

  const success =
    transaction.status.success === true;

  const finished =
    new Date().toISOString();

  db.prepare(`
    UPDATE mainnet_transfers
    SET
      state = ?,
      tx_digest = ?,
      submitted_at = ?,
      confirmed_at = ?,
      updated_at = ?
    WHERE submission_key = ?
      AND tx_digest IS NULL
  `).run(
    success ? "confirmed" : "failed",
    transaction.digest,
    finished,
    success ? finished : null,
    finished,
    submissionKey,
  );

  const updated =
    getMainnetTransfer(submissionKey);

  if (!updated) {
    throw new Error(
      "Mainnet transfer journal disappeared"
    );
  }

  return updated;
}


async function verifyMainnetSuiPayment(
  requested: SuiPaymentVerificationInput,
) {
  const client = mainnetClient();

  await client.waitForTransaction({
    digest: requested.tx_digest,
    timeout: 60_000,
  });

  const result =
    await client.getTransaction({
      digest: requested.tx_digest,
      include: {
        effects: true,
        balanceChanges: true,
        transaction: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Mainnet Sui payment transaction not found"
    );
  }

  if (
    transaction.digest
    !== requested.tx_digest
  ) {
    throw new Error(
      "Mainnet Sui payment digest mismatch"
    );
  }

  if (
    transaction.status.success
    !== true
  ) {
    throw new Error(
      "Mainnet Sui payment transaction failed"
    );
  }

  const transactionData =
    (
      transaction as unknown as {
        transaction?: {
          sender?: unknown;
        };
      }
    ).transaction;

  const senderAddress =
    String(
      transactionData?.sender ?? ""
    )
      .trim()
      .toLowerCase();

  if (
    !/^0x[0-9a-f]{64}$/.test(
      senderAddress
    )
  ) {
    throw new Error(
      "Mainnet Sui payment sender is invalid"
    );
  }

  /*
   * Keep this intentionally read-only.
   *
   * The gRPC SDK representation has changed across
   * versions, so normalize the returned balance-change
   * objects rather than binding settlement logic to one
   * generated TypeScript shape.
   */
  const balanceChanges =
    (
      transaction as unknown as {
        balanceChanges?: unknown[];
      }
    ).balanceChanges || [];

  let receivedMist = 0n;

  for (
    const rawChange of balanceChanges
  ) {
    if (
      !rawChange ||
      typeof rawChange !== "object"
    ) {
      continue;
    }

    const change =
      rawChange as Record<string, unknown>;

    const coinType = String(
      change.coinType ??
      change.coin_type ??
      ""
    );

    if (
      coinType
      !== "0x2::sui::SUI"
      &&
      coinType
      !== (
        "0x00000000000000000000000000000000" +
        "00000000000000000000000000000002" +
        "::sui::SUI"
      )
    ) {
      continue;
    }

    let address = "";

    if (
      typeof change.address === "string"
    ) {
      address = change.address;
    } else if (
      change.owner &&
      typeof change.owner === "object"
    ) {
      const owner =
        change.owner as Record<string, unknown>;

      address = String(
        owner.AddressOwner ??
        owner.addressOwner ??
        owner.address ??
        ""
      );
    }

    address = address
      .trim()
      .toLowerCase();

    if (
      address
      !== requested.recipient_address
    ) {
      continue;
    }

    const amountRaw =
      change.amount ??
      change.amountMist ??
      change.amount_mist;

    if (
      amountRaw === undefined ||
      amountRaw === null
    ) {
      continue;
    }

    const amount = BigInt(
      String(amountRaw)
    );

    if (amount > 0n) {
      receivedMist += amount;
    }
  }

  const minimum =
    BigInt(
      requested.minimum_amount_mist
    );

  return {
    network: "mainnet",
    tx_digest:
      requested.tx_digest,
    sender_address:
      senderAddress,
    success: true,
    recipient_address:
      requested.recipient_address,
    coin_type: "0x2::sui::SUI",
    received_mist:
      receivedMist.toString(),
    minimum_amount_mist:
      minimum.toString(),
    sufficient:
      receivedMist >= minimum,
  };
}


async function prepareTestnetProbe(
  submissionKey: string,
): Promise<DeliveryRow> {
  if (!TESTNET_PREPARE_ENABLED) {
    throw new Error(
      "Testnet transaction preparation is disabled"
    );
  }

  const existing = getDelivery(submissionKey);

  if (
    existing?.transaction_bytes_b64 &&
    existing?.signature
  ) {
    // Critical invariant:
    // once signed material exists, NEVER rebuild it.
    return existing;
  }

  const keypair = requireTestnetSigner();
  const sender = keypair.toSuiAddress();

  const amountBaseUnits = "1000000";
  const coinType = "0x2::sui::SUI";
  const now = new Date().toISOString();

  if (!existing) {
    db.prepare(`
      INSERT INTO deliveries (
        submission_key,
        chain,
        coin_type,
        recipient_address,
        amount_base_units,
        state,
        sender_address,
        transaction_bytes_b64,
        signature,
        tx_digest,
        prepared_at,
        submitted_at,
        confirmed_at,
        created_at,
        updated_at
      )
      VALUES (
        ?, ?, ?, ?, ?, ?,
        ?, NULL, NULL, NULL,
        NULL, NULL, NULL, ?, ?
      )
    `).run(
      submissionKey,
      "sui",
      coinType,
      sender,
      amountBaseUnits,
      "preparing",
      sender,
      now,
      now,
    );
  } else {
    if (
      existing.chain !== "sui" ||
      existing.coin_type !== coinType ||
      existing.recipient_address !== sender ||
      existing.amount_base_units !== amountBaseUnits
    ) {
      throw new Error(
        "Existing submission_key has different immutable data"
      );
    }

    if (
      existing.state !== "preparing" &&
      existing.state !== "prepared"
    ) {
      throw new Error(
        `Cannot prepare delivery in state ${existing.state}`
      );
    }
  }

  const tx = new Transaction();
  tx.setSender(sender);

  const [coin] = tx.splitCoins(
    tx.gas,
    [Number(amountBaseUnits)],
  );

  tx.transferObjects([coin], sender);

  const client = testnetClient();

  const bytes = await tx.build({
    client,
  });

  const signed =
    await keypair.signTransaction(bytes);

  const bytesB64 =
    Buffer.from(bytes).toString("base64");

  const preparedAt =
    new Date().toISOString();

  const update = db.prepare(`
    UPDATE deliveries
    SET
      state = 'prepared',
      sender_address = ?,
      transaction_bytes_b64 = ?,
      signature = ?,
      prepared_at = ?,
      updated_at = ?
    WHERE submission_key = ?
      AND tx_digest IS NULL
  `).run(
    sender,
    bytesB64,
    signed.signature,
    preparedAt,
    preparedAt,
    submissionKey,
  );

  if (update.changes !== 1) {
    throw new Error(
      "Prepared transaction journal update failed"
    );
  }

  const prepared =
    getDelivery(submissionKey);

  if (!prepared) {
    throw new Error(
      "Prepared delivery disappeared from journal"
    );
  }

  return prepared;
}

async function reconcileCreatorPublication(
  publicationKey: string,
): Promise<CreatorPublicationRow> {
  const row =
    getCreatorPublication(publicationKey);

  if (!row) {
    throw new Error(
      "Creator publication not found"
    );
  }

  if (
    row.state === "confirmed" &&
    row.package_id &&
    row.coin_type
  ) {
    return row;
  }

  if (!row.tx_digest) {
    throw new Error(
      "Creator publication has no transaction digest"
    );
  }

  const client =
    creatorPublicationClient(
      row.network
    );

  await client.waitForTransaction({
    digest: row.tx_digest,
    timeout: 60_000,
  });

  const result =
    await client.getTransaction({
      digest: row.tx_digest,
      include: {
        effects: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Sui creator publication reconciliation returned no transaction"
    );
  }

  if (transaction.digest !== row.tx_digest) {
    throw new Error(
      "Reconciled creator publication digest does not match journal"
    );
  }

  if (transaction.status.success !== true) {
    throw new Error(
      "Creator publication transaction failed on Sui"
    );
  }

  const effects = transaction.effects;

  if (!effects) {
    throw new Error(
      "Creator publication transaction has no effects"
    );
  }

  if (
    effects.transactionDigest !==
    row.tx_digest
  ) {
    throw new Error(
      "Creator publication effects digest does not match journal"
    );
  }

  const publishedPackages =
    effects.changedObjects.filter(
      (changed) =>
        changed.outputState === "PackageWrite" &&
        changed.idOperation === "Created",
    );

  if (publishedPackages.length !== 1) {
    throw new Error(
      `Expected exactly one published package; found ${publishedPackages.length}`
    );
  }

  const packageId =
    publishedPackages[0].objectId;

  const coinType =
    `${packageId}::${row.module_name}::${row.coin_struct_name}`;

  const now =
    new Date().toISOString();

  const update = db.prepare(`
    UPDATE creator_publications
    SET
      state = 'confirmed',
      package_id = ?,
      coin_type = ?,
      confirmed_at = ?,
      updated_at = ?
    WHERE publication_key = ?
      AND tx_digest = ?
      AND package_id IS NULL
      AND coin_type IS NULL
  `).run(
    packageId,
    coinType,
    now,
    now,
    publicationKey,
    row.tx_digest,
  );

  if (update.changes !== 1) {
    const raced =
      getCreatorPublication(publicationKey);

    if (
      raced?.state === "confirmed" &&
      raced.package_id &&
      raced.coin_type
    ) {
      return raced;
    }

    throw new Error(
      "Creator publication reconciliation journal update failed"
    );
  }

  const confirmed =
    getCreatorPublication(publicationKey);

  if (!confirmed) {
    throw new Error(
      "Confirmed creator publication disappeared from journal"
    );
  }

  return confirmed;
}

async function recoverCreatorPublication(
  publicationKey: string,
  txDigest: string,
): Promise<CreatorPublicationRow> {
  const row =
    getCreatorPublication(publicationKey);

  if (!row) {
    throw new Error(
      "Creator publication not found"
    );
  }

  if (!txDigest) {
    throw new Error(
      "Transaction digest is required"
    );
  }

  if (
    row.state === "confirmed" &&
    row.tx_digest === txDigest &&
    row.package_id &&
    row.coin_type
  ) {
    return row;
  }

  if (
    row.tx_digest &&
    row.tx_digest !== txDigest
  ) {
    throw new Error(
      "Creator publication already has a different transaction digest"
    );
  }

  const client =
    creatorPublicationClient(
      row.network
    );

  await client.waitForTransaction({
    digest: txDigest,
    timeout: 60_000,
  });

  const result =
    await client.getTransaction({
      digest: txDigest,
      include: {
        effects: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Sui recovery returned no transaction"
    );
  }

  if (transaction.digest !== txDigest) {
    throw new Error(
      "Recovered transaction digest does not match requested digest"
    );
  }

  if (transaction.status.success !== true) {
    throw new Error(
      "Recovered creator publication transaction failed on Sui"
    );
  }

  const effects = transaction.effects;

  if (!effects) {
    throw new Error(
      "Recovered creator publication has no transaction effects"
    );
  }

  if (
    effects.transactionDigest !==
    txDigest
  ) {
    throw new Error(
      "Recovered effects digest does not match requested digest"
    );
  }

  const publishedPackages =
    effects.changedObjects.filter(
      (changed) =>
        changed.outputState === "PackageWrite" &&
        changed.idOperation === "Created",
    );

  if (publishedPackages.length !== 1) {
    throw new Error(
      `Expected exactly one published package; found ${publishedPackages.length}`
    );
  }

  const packageId =
    publishedPackages[0].objectId;

  const coinType =
    `${packageId}::${row.module_name}::${row.coin_struct_name}`;

  const now =
    new Date().toISOString();

  const update = db.prepare(`
    UPDATE creator_publications
    SET
      state = 'confirmed',
      tx_digest = ?,
      package_id = ?,
      coin_type = ?,
      submitted_at = COALESCE(submitted_at, ?),
      confirmed_at = COALESCE(confirmed_at, ?),
      updated_at = ?
    WHERE publication_key = ?
      AND (
        tx_digest IS NULL OR
        tx_digest = ?
      )
  `).run(
    txDigest,
    packageId,
    coinType,
    now,
    now,
    now,
    publicationKey,
    txDigest,
  );

  if (update.changes !== 1) {
    const raced =
      getCreatorPublication(publicationKey);

    if (
      raced?.state === "confirmed" &&
      raced.tx_digest === txDigest &&
      raced.package_id === packageId &&
      raced.coin_type === coinType
    ) {
      return raced;
    }

    throw new Error(
      "Creator publication recovery journal update failed"
    );
  }

  const recovered =
    getCreatorPublication(publicationKey);

  if (!recovered) {
    throw new Error(
      "Recovered creator publication disappeared from journal"
    );
  }

  return recovered;
}

async function registerCreatorCurrency(
  publicationKey: string,
): Promise<CreatorPublicationRow> {
  const publication =
    getCreatorPublication(publicationKey);

  if (!publication) {
    throw new Error(
      "Creator publication not found"
    );
  }

  const hasAnyRegistration =
    publication.registration_tx_digest !== null ||
    publication.registered_currency_object_id !== null ||
    publication.registered_at !== null;

  const hasCompleteRegistration =
    publication.registration_tx_digest !== null &&
    publication.registered_currency_object_id !== null &&
    publication.registered_at !== null;

  if (
    hasAnyRegistration &&
    !hasCompleteRegistration
  ) {
    throw new Error(
      "Creator Currency registration journal is incomplete"
    );
  }

  if (hasCompleteRegistration) {
    const verifiedCurrencyObjectId =
      await verifyCreatorCurrencyRegistration(
        publication,
        publication.registration_tx_digest!,
      );

    if (
      verifiedCurrencyObjectId !==
      publication.registered_currency_object_id
    ) {
      throw new Error(
        "Registered creator Currency object conflicts with journal"
      );
    }

    return publication;
  }

  if (
    publication.state !== "confirmed" ||
    !publication.coin_type ||
    !publication.tx_digest
  ) {
    throw new Error(
      "Creator publication has no confirmed on-chain identity"
    );
  }

  const signer =
    requireCreatorCurrencyRegistrationSigner(
      publication.network
    );

  const client =
    creatorPublicationClient(
      publication.network
    );

  const supply =
    await getCreatorPublicationSupply(
      publicationKey
    );

  const tx = new Transaction();

  tx.moveCall({
    target:
      "0x2::coin_registry::finalize_registration",
    typeArguments: [
      publication.coin_type,
    ],
    arguments: [
      tx.object(
        "0x000000000000000000000000000000000000000000000000000000000000000c"
      ),
      tx.object(
        supply.currency_object_id
      ),
    ],
  });

  const result =
    await client.signAndExecuteTransaction({
      signer,
      transaction: tx,
      include: {
        effects: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Creator Currency registration returned no transaction"
    );
  }

  if (
    transaction.status.success !== true
  ) {
    throw new Error(
      "Creator Currency registration transaction failed"
    );
  }

  return recoverCreatorCurrencyRegistration(
    publicationKey,
    transaction.digest,
  );
}


async function recoverCreatorMetadataCap(
  publicationKey: string,
): Promise<CreatorPublicationRow> {
  const publication =
    getCreatorPublication(publicationKey);

  if (!publication) {
    throw new Error(
      "Creator publication not found"
    );
  }

  if (
    publication.state !== "confirmed" ||
    !publication.coin_type ||
    !publication.tx_digest ||
    !publication.recipient_address
  ) {
    throw new Error(
      "Creator publication has no confirmed metadata identity"
    );
  }

  const client =
    creatorPublicationClient(
      publication.network
    );

  if (publication.metadata_cap_object_id) {
    const { object } =
      await client.getObject({
        objectId:
          publication.metadata_cap_object_id,
      });

    const expectedMetadataCapType =
      `0x0000000000000000000000000000000000000000000000000000000000000002` +
      `::coin_registry::MetadataCap<${publication.coin_type}>`;

    if (
      object.type !==
      expectedMetadataCapType
    ) {
      throw new Error(
        "Creator MetadataCap type mismatch"
      );
    }

    if (
      object.owner?.AddressOwner?.toLowerCase() !==
      publication.recipient_address.toLowerCase()
    ) {
      throw new Error(
        "Creator MetadataCap owner mismatch"
      );
    }

    return publication;
  }

  const result =
    await client.getTransaction({
      digest: publication.tx_digest,
      include: {
        effects: true,
        objectTypes: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Creator publication transaction not found"
    );
  }

  if (
    transaction.digest !==
    publication.tx_digest
  ) {
    throw new Error(
      "Creator publication transaction digest mismatch"
    );
  }

  if (
    transaction.status.success !== true
  ) {
    throw new Error(
      "Creator publication transaction failed on Sui"
    );
  }

  const expectedMetadataCapType =
    `0x0000000000000000000000000000000000000000000000000000000000000002` +
    `::coin_registry::MetadataCap<${publication.coin_type}>`;

  const caps =
    transaction.effects?.changedObjects.filter(
      (changed) =>
        changed.outputState === "ObjectWrite" &&
        changed.idOperation === "Created" &&
        transaction.objectTypes?.[
          changed.objectId
        ] === expectedMetadataCapType,
    ) ?? [];

  if (caps.length !== 1) {
    throw new Error(
      `Expected exactly one creator MetadataCap; found ${caps.length}`
    );
  }

  const metadataCapObjectId =
    caps[0].objectId;

  const { object } =
    await client.getObject({
      objectId:
        metadataCapObjectId,
    });

  if (
    object.type !==
    expectedMetadataCapType
  ) {
    throw new Error(
      "Creator MetadataCap type mismatch"
    );
  }

  if (
    object.owner?.AddressOwner?.toLowerCase() !==
    publication.recipient_address.toLowerCase()
  ) {
    throw new Error(
      "Creator MetadataCap owner mismatch"
    );
  }

  const now =
    new Date().toISOString();

  const update = db.prepare(`
    UPDATE creator_publications
    SET
      metadata_cap_object_id = ?,
      updated_at = ?
    WHERE publication_key = ?
      AND metadata_cap_object_id IS NULL
  `).run(
    metadataCapObjectId,
    now,
    publicationKey,
  );

  if (update.changes !== 1) {
    const raced =
      getCreatorPublication(publicationKey);

    if (
      raced?.metadata_cap_object_id ===
      metadataCapObjectId
    ) {
      return raced;
    }

    throw new Error(
      "Creator MetadataCap journal update failed"
    );
  }

  const recovered =
    getCreatorPublication(publicationKey);

  if (!recovered) {
    throw new Error(
      "Recovered creator MetadataCap disappeared from journal"
    );
  }

  return recovered;
}


async function verifyCreatorCurrencyRegistration(
  publication: CreatorPublicationRow,
  registrationTxDigest: string,
): Promise<string> {
  if (
    publication.state !== "confirmed" ||
    !publication.coin_type ||
    !publication.tx_digest
  ) {
    throw new Error(
      "Creator publication has no confirmed on-chain identity"
    );
  }

  if (!registrationTxDigest) {
    throw new Error(
      "Creator Currency registration digest is required"
    );
  }

  const client =
    creatorPublicationClient(
      publication.network
    );

  await client.waitForTransaction({
    digest: registrationTxDigest,
    timeout: 60_000,
  });

  const result =
    await client.getTransaction({
      digest: registrationTxDigest,
      include: {
        effects: true,
        objectTypes: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Creator Currency registration transaction not found"
    );
  }

  if (
    transaction.digest !==
    registrationTxDigest
  ) {
    throw new Error(
      "Creator Currency registration digest mismatch"
    );
  }

  if (transaction.status.success !== true) {
    throw new Error(
      "Creator Currency registration transaction failed on Sui"
    );
  }

  const expectedCurrencyType =
    `0x0000000000000000000000000000000000000000000000000000000000000002` +
    `::coin_registry::Currency<${publication.coin_type}>`;

  const createdCurrencies =
    transaction.effects?.changedObjects.filter(
      (changed) =>
        changed.outputState === "ObjectWrite" &&
        changed.idOperation === "Created" &&
        transaction.objectTypes?.[
          changed.objectId
        ] === expectedCurrencyType,
    ) ?? [];

  if (createdCurrencies.length !== 1) {
    throw new Error(
      `Expected exactly one registered creator Currency object; found ${createdCurrencies.length}`
    );
  }

  const registeredCurrencyObjectId =
    createdCurrencies[0].objectId;

  const { object } =
    await client.getObject({
      objectId:
        registeredCurrencyObjectId,
      include: {
        owner: true,
        type: true,
        previousTransaction: true,
      },
    });

  if (
    object.type !==
    expectedCurrencyType
  ) {
    throw new Error(
      "Registered creator Currency type mismatch"
    );
  }

  if (
    object.previousTransaction !==
    registrationTxDigest
  ) {
    throw new Error(
      "Registered creator Currency transaction mismatch"
    );
  }

  if (
    object.owner?.$kind !== "Shared"
  ) {
    throw new Error(
      "Registered creator Currency is not shared"
    );
  }

  return registeredCurrencyObjectId;
}


async function recoverCreatorCurrencyRegistration(
  publicationKey: string,
  registrationTxDigest: string,
): Promise<CreatorPublicationRow> {
  const publication =
    getCreatorPublication(publicationKey);

  if (!publication) {
    throw new Error(
      "Creator publication not found"
    );
  }

  if (!registrationTxDigest) {
    throw new Error(
      "Creator Currency registration digest is required"
    );
  }

  const hasAnyRegistration =
    publication.registration_tx_digest !== null ||
    publication.registered_currency_object_id !== null ||
    publication.registered_at !== null;

  const hasCompleteRegistration =
    publication.registration_tx_digest !== null &&
    publication.registered_currency_object_id !== null &&
    publication.registered_at !== null;

  if (
    hasAnyRegistration &&
    !hasCompleteRegistration
  ) {
    throw new Error(
      "Creator Currency registration journal is incomplete"
    );
  }

  if (hasCompleteRegistration) {
    if (
      publication.registration_tx_digest !==
      registrationTxDigest
    ) {
      throw new Error(
        "Creator Currency registration digest conflicts with journal"
      );
    }

    const verifiedCurrencyObjectId =
      await verifyCreatorCurrencyRegistration(
        publication,
        registrationTxDigest,
      );

    if (
      verifiedCurrencyObjectId !==
      publication.registered_currency_object_id
    ) {
      throw new Error(
        "Registered creator Currency object conflicts with journal"
      );
    }

    return publication;
  }

  const registeredCurrencyObjectId =
    await verifyCreatorCurrencyRegistration(
      publication,
      registrationTxDigest,
    );

  const now =
    new Date().toISOString();

  const update = db.prepare(`
    UPDATE creator_publications
    SET
      registration_tx_digest = ?,
      registered_currency_object_id = ?,
      registered_at = ?,
      updated_at = ?
    WHERE publication_key = ?
      AND registration_tx_digest IS NULL
      AND registered_currency_object_id IS NULL
      AND registered_at IS NULL
  `).run(
    registrationTxDigest,
    registeredCurrencyObjectId,
    now,
    now,
    publicationKey,
  );

  if (update.changes !== 1) {
    const raced =
      getCreatorPublication(publicationKey);

    if (
      raced?.registration_tx_digest ===
        registrationTxDigest &&
      raced.registered_currency_object_id ===
        registeredCurrencyObjectId &&
      raced.registered_at
    ) {
      return raced;
    }

    throw new Error(
      "Creator Currency registration journal update failed"
    );
  }

  const recovered =
    getCreatorPublication(publicationKey);

  if (!recovered) {
    throw new Error(
      "Recovered creator Currency registration disappeared from journal"
    );
  }

  return recovered;
}


async function getCreatorPublicationSupply(
  publicationKey: string,
) {
  const publication =
    getCreatorPublication(publicationKey);

  if (!publication) {
    throw new Error(
      "Creator publication not found"
    );
  }

  if (publication.state !== "confirmed") {
    throw new Error(
      "Creator publication is not confirmed"
    );
  }

  if (
    !publication.coin_type ||
    !publication.tx_digest
  ) {
    throw new Error(
      "Confirmed creator publication has no on-chain identity"
    );
  }

  const client =
    creatorPublicationClient(
      publication.network
    );

  const expectedCurrencyType =
    `0x0000000000000000000000000000000000000000000000000000000000000002` +
    `::coin_registry::Currency<${publication.coin_type}>`;

  let currencyObjectId: string;
  let expectedPreviousTransaction: string;
  let requireShared = false;

  if (
    publication.registered_currency_object_id &&
    publication.registration_tx_digest &&
    publication.registered_at
  ) {
    currencyObjectId =
      publication.registered_currency_object_id;

    expectedPreviousTransaction =
      publication.registration_tx_digest;

    requireShared = true;
  } else {
    const transactionResult =
      await client.getTransaction({
        digest: publication.tx_digest,
        include: {
          effects: true,
          objectTypes: true,
        },
      });

    const transaction =
      transactionResult.Transaction ??
      transactionResult.FailedTransaction;

    if (!transaction) {
      throw new Error(
        "Creator publication transaction not found"
      );
    }

    if (
      transaction.digest !==
      publication.tx_digest
    ) {
      throw new Error(
        "Creator publication transaction digest mismatch"
      );
    }

    if (transaction.status.success !== true) {
      throw new Error(
        "Creator publication transaction failed on Sui"
      );
    }

    const currencyObjects =
      transaction.effects?.changedObjects.filter(
        (changed) =>
          changed.outputState === "ObjectWrite" &&
          changed.idOperation === "Created" &&
          transaction.objectTypes?.[
            changed.objectId
          ] === expectedCurrencyType,
      ) ?? [];

    if (currencyObjects.length !== 1) {
      throw new Error(
        `Expected exactly one creator Currency object; found ${currencyObjects.length}`
      );
    }

    currencyObjectId =
      currencyObjects[0].objectId;

    expectedPreviousTransaction =
      publication.tx_digest;
  }

  const { object } =
    await client.getObject({
      objectId: currencyObjectId,
      include: {
        json: true,
        owner: true,
        previousTransaction: true,
      },
    });

  if (object.type !== expectedCurrencyType) {
    throw new Error(
      "Creator Currency object type mismatch"
    );
  }

  if (
    object.previousTransaction !==
    expectedPreviousTransaction
  ) {
    throw new Error(
      "Creator Currency transaction mismatch"
    );
  }

  if (
    requireShared &&
    object.owner?.$kind !== "Shared"
  ) {
    throw new Error(
      "Registered creator Currency is not shared"
    );
  }

  const json = object.json;

  if (!json) {
    throw new Error(
      "Creator Currency object has no JSON representation"
    );
  }

  const decimals = json.decimals;
  const symbol = json.symbol;
  const supply = json.supply;

  if (
    typeof decimals !== "number" ||
    typeof symbol !== "string" ||
    !supply ||
    typeof supply !== "object"
  ) {
    throw new Error(
      "Creator Currency object has invalid supply metadata"
    );
  }

  const supplyRecord =
    supply as Record<string, unknown>;

  if (
    supplyRecord["@variant"] !== "Fixed"
  ) {
    throw new Error(
      "Creator Currency supply is not fixed"
    );
  }

  const fixedSupply =
    supplyRecord["pos0"];

  if (
    !fixedSupply ||
    typeof fixedSupply !== "object"
  ) {
    throw new Error(
      "Creator Currency fixed supply value is missing"
    );
  }

  const fixedSupplyRecord =
    fixedSupply as Record<string, unknown>;

  const supplyBaseUnits =
    fixedSupplyRecord["value"];

  if (
    typeof supplyBaseUnits !== "string" ||
    !/^[0-9]+$/.test(supplyBaseUnits)
  ) {
    throw new Error(
      "Creator Currency fixed supply value is invalid"
    );
  }

  return {
    publication_key:
      publication.publication_key,
    coin_type:
      publication.coin_type,
    currency_object_id:
      currencyObjectId,
    decimals,
    symbol,
    supply_state: "fixed",
    supply_base_units:
      supplyBaseUnits,
    previous_transaction:
      object.previousTransaction,
    registered:
      requireShared,
  };
}

async function submitPreparedTestnetProbe(
  submissionKey: string,
): Promise<DeliveryRow> {
  if (!TESTNET_SUBMIT_ENABLED) {
    throw new Error(
      "Testnet transaction submission is disabled"
    );
  }

  const row = getDelivery(submissionKey);

  if (!row) {
    throw new Error("Delivery not found");
  }

  if (row.tx_digest) {
    // Never re-execute a journal entry that already
    // has an authoritative chain digest.
    return row;
  }

  if (row.state !== "prepared") {
    throw new Error(
      `Expected prepared state; found ${row.state}`
    );
  }

  if (
    !row.transaction_bytes_b64 ||
    !row.signature
  ) {
    throw new Error(
      "Prepared transaction material is missing"
    );
  }

  const bytes = Buffer.from(
    row.transaction_bytes_b64,
    "base64",
  );

  const result =
    await testnetClient().executeTransaction({
      transaction: bytes,
      signatures: [row.signature],
      include: {
        effects: true,
        balanceChanges: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Sui execution returned no transaction"
    );
  }

  const now = new Date().toISOString();
  const success =
    transaction.status.success === true;

  const state =
    success ? "submitted" : "failed";

  const update = db.prepare(`
    UPDATE deliveries
    SET
      state = ?,
      tx_digest = ?,
      submitted_at = ?,
      updated_at = ?
    WHERE submission_key = ?
      AND tx_digest IS NULL
  `).run(
    state,
    transaction.digest,
    now,
    now,
    submissionKey,
  );

  if (update.changes !== 1) {
    throw new Error(
      "Submission journal update failed"
    );
  }

  const updated =
    getDelivery(submissionKey);

  if (!updated) {
    throw new Error(
      "Submitted delivery disappeared"
    );
  }

  return updated;
}


async function reconcileTestnetProbe(
  submissionKey: string,
): Promise<DeliveryRow> {
  const row = getDelivery(submissionKey);

  if (!row) {
    throw new Error("Delivery not found");
  }

  if (row.state === "confirmed") {
    return row;
  }

  if (!row.tx_digest) {
    throw new Error(
      "Delivery has no transaction digest"
    );
  }

  const client = testnetClient();

  await client.waitForTransaction({
    digest: row.tx_digest,
    timeout: 60_000,
  });

  const result =
    await client.getTransaction({
      digest: row.tx_digest,
      include: {
        effects: true,
        balanceChanges: true,
        transaction: true,
      },
    });

  const transaction =
    result.Transaction ??
    result.FailedTransaction;

  if (!transaction) {
    throw new Error(
      "Sui reconciliation returned no transaction"
    );
  }

  if (transaction.digest !== row.tx_digest) {
    throw new Error(
      "Reconciled digest does not match journal"
    );
  }

  const success =
    transaction.status.success === true;

  const state =
    success ? "confirmed" : "failed";

  const now = new Date().toISOString();

  db.prepare(`
    UPDATE deliveries
    SET
      state = ?,
      confirmed_at = ?,
      updated_at = ?
    WHERE submission_key = ?
      AND tx_digest = ?
  `).run(
    state,
    success ? now : null,
    now,
    submissionKey,
    row.tx_digest,
  );

  const updated =
    getDelivery(submissionKey);

  if (!updated) {
    throw new Error(
      "Reconciled delivery disappeared"
    );
  }

  return updated;
}


const app = express();

app.disable("x-powered-by");
app.use(express.json({ limit: "32kb" }));

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "fanz-sui",
    adapter: "mock",
  });
});

app.use("/v1", authenticate);

app.post(
  "/v1/mainnet/starter-grants",
  async (req, res) => {
    try {
      const body =
        (
          req.body &&
          typeof req.body === "object"
        )
          ? req.body as Record<string, unknown>
          : {};

      const submissionKey =
        String(
          body.submission_key || ""
        ).trim();

      const recipientAddress =
        String(
          body.recipient_address || ""
        ).trim();

      const transfer =
        await executeMainnetStarterGrant({
          submissionKey,
          recipientAddress,
        });

      res.json({
        grant: {
          ...publicMainnetTransfer(
            transfer
          ),
          amount_sui: "0.25",
        },
      });

    } catch (error) {
      res.status(422).json({
        error:
          error instanceof Error
            ? error.message
            : "Starter grant failed",
      });
    }
  },
);


app.post(
  "/v1/mainnet/treasury/canary",
  async (_req, res) => {
    try {
      const key =
        "treasury-canary-"
        + new Date()
            .toISOString()
            .replace(/[:.]/g, "-");

      const transfer =
        await executeMainnetTreasuryTransfer({
          submissionKey: key,
          purpose: "treasury_canary",
          amountMist: 10_000_000n,
        });

      res.json({
        transfer:
          publicMainnetTransfer(transfer),
      });

    } catch (error) {
      res.status(422).json({
        error:
          error instanceof Error
            ? error.message
            : "Treasury canary failed",
      });
    }
  },
);


app.post(
  "/v1/mainnet/treasury/sweep",
  async (_req, res) => {
    try {
      const hotAddress =
        (
          process.env
            .FANZ_SUI_MAINNET_HOT_ADDRESS ||
          ""
        ).trim().toLowerCase();

      const client = mainnetClient();

      const result =
        await client.getBalance({
          owner: hotAddress,
          coinType: "0x2::sui::SUI",
        });

      const balanceMist =
        BigInt(
          result.balance?.addressBalance ??
          result.balance?.balance ??
          "0"
        );

      const sweepMist =
        calculateMainnetTreasurySweep(
          balanceMist
        );

      if (sweepMist <= 0n) {
        res.json({
          action:
            "NO_SWEEP_BELOW_FLOOR",
          balance_mist:
            balanceMist.toString(),
          sweep_mist: "0",
        });
        return;
      }

      const day =
        new Date()
          .toISOString()
          .slice(0, 10);

      const transfer =
        await executeMainnetTreasuryTransfer({
          submissionKey:
            `treasury-sweep-${day}`,
          purpose: "treasury_sweep",
          amountMist: sweepMist,
        });

      res.json({
        action: "SWEEP",
        opening_balance_mist:
          balanceMist.toString(),
        transfer:
          publicMainnetTransfer(transfer),
      });

    } catch (error) {
      res.status(422).json({
        error:
          error instanceof Error
            ? error.message
            : "Treasury sweep failed",
      });
    }
  },
);


app.get(
  "/v1/mainnet/treasury/sweep-preview",
  async (_req, res) => {
    try {
      const hotAddress =
        (
          process.env.FANZ_SUI_MAINNET_HOT_ADDRESS ||
          ""
        ).trim().toLowerCase();

      if (
        !/^0x[0-9a-f]{64}$/.test(
          hotAddress
        )
      ) {
        throw new Error(
          "FANZ_SUI_MAINNET_HOT_ADDRESS "
          + "is not configured"
        );
      }

      const client = mainnetClient();

      const result =
        await client.getBalance({
          owner: hotAddress,
          coinType: "0x2::sui::SUI",
        });

      const balanceMist =
        BigInt(
          result.balance?.addressBalance ??
          result.balance?.balance ??
          "0"
        );

      const sweepMist =
        calculateMainnetTreasurySweep(
          balanceMist
        );

      res.json({
        network: "mainnet",
        hot_address: hotAddress,
        balance_mist:
          balanceMist.toString(),
        floor_mist:
          MAINNET_SWEEP_FLOOR_MIST.toString(),
        sweep_excess_bps:
          MAINNET_SWEEP_EXCESS_BPS.toString(),
        sweep_mist:
          sweepMist.toString(),
        retained_mist:
          (
            balanceMist - sweepMist
          ).toString(),
        action:
          sweepMist > 0n
            ? "SWEEP"
            : "NO_SWEEP_BELOW_FLOOR",
      });

    } catch (error) {
      res.status(422).json({
        error:
          error instanceof Error
            ? error.message
            : "Unable to preview treasury sweep",
      });
    }
  },
);

app.post(
  "/v1/payments/quote",
  async (req, res) => {
    try {
      const body =
        (
          req.body &&
          typeof req.body === "object"
        )
          ? req.body as Record<
              string,
              unknown
            >
          : {};

      const amountUsd =
        Number(
          body.amount_usd
        );

      const quote =
        await quoteMainnetSuiPayment(
          amountUsd
        );

      res.json({
        quote,
      });

    } catch (error) {
      res.status(422).json({
        error:
          error instanceof Error
            ? error.message
            : (
                "Unable to quote "
                + "mainnet Sui payment"
              ),
      });
    }
  },
);

app.post(
  "/v1/payments/verify",
  async (req, res) => {
    let requested:
      SuiPaymentVerificationInput;

    try {
      requested =
        validateSuiPaymentVerification(
          req.body
        );
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "invalid request",
      });
      return;
    }

    try {
      const verification =
        await verifyMainnetSuiPayment(
          requested
        );

      res.json({
        verification,
      });
    } catch (error) {
      res.status(422).json({
        error:
          error instanceof Error
            ? error.message
            : (
                "Unable to verify "
                + "mainnet Sui payment"
              ),
      });
    }
  },
);


app.post("/v1/deliveries", (req, res) => {
  let requested: DeliveryInput;

  try {
    requested = validateDelivery(req.body);
  } catch (error) {
    res.status(400).json({
      error: error instanceof Error ? error.message : "invalid request",
    });
    return;
  }

  const existing = getDelivery(requested.submission_key);

  if (existing) {
    if (!immutableFieldsMatch(existing, requested)) {
      res.status(409).json({
        error: "submission_key already exists with different immutable data",
        delivery: publicDelivery(existing),
      });
      return;
    }

    res.json({
      created: false,
      delivery: publicDelivery(existing),
    });
    return;
  }

  const now = new Date().toISOString();

  // Mock-only public sender identity.
  // No private key and no chain transaction exist in v0.
  const senderAddress =
    "mock:" +
    crypto
      .createHash("sha256")
      .update(requested.submission_key)
      .digest("hex")
      .slice(0, 32);

  db.prepare(`
    INSERT INTO deliveries (
      submission_key,
      chain,
      coin_type,
      recipient_address,
      amount_base_units,
      state,
      sender_address,
      transaction_bytes_b64,
      signature,
      tx_digest,
      prepared_at,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    )
    VALUES (
      ?, ?, ?, ?, ?, ?, ?,
      NULL, NULL, NULL,
      ?, NULL, NULL, ?, ?
    )
  `).run(
    requested.submission_key,
    requested.chain,
    requested.coin_type,
    requested.recipient_address,
    requested.amount_base_units,
    "prepared",
    senderAddress,
    now,
    now,
    now,
  );

  res.status(201).json({
    created: true,
    delivery: publicDelivery(
      getDelivery(requested.submission_key)!
    ),
  });
});

app.get("/v1/deliveries/:submissionKey", (req, res) => {
  const delivery = getDelivery(req.params.submissionKey);

  if (!delivery) {
    res.status(404).json({ error: "delivery not found" });
    return;
  }

  res.json({
    delivery: publicDelivery(delivery),
  });
});


app.post("/v1/creator-publications", (req, res) => {
  let requested: CreatorPublicationInput;

  try {
    requested = validateCreatorPublication(req.body);
  } catch (error) {
    res.status(400).json({
      error:
        error instanceof Error
          ? error.message
          : "invalid request",
    });
    return;
  }

  const existing =
    getCreatorPublication(requested.publication_key);

  if (existing) {
    if (
      !creatorPublicationImmutableFieldsMatch(
        existing,
        requested,
      )
    ) {
      res.status(409).json({
        error:
          "publication_key already exists with different immutable data",
        publication:
          publicCreatorPublication(existing),
      });
      return;
    }

    res.json({
      created: false,
      publication:
        publicCreatorPublication(existing),
    });
    return;
  }

  const now = new Date().toISOString();

  db.prepare(`
    INSERT INTO creator_publications (
      publication_key,
      chain,
      network,
      recipient_address,
      module_name,
      coin_struct_name,
      source_sha256,
      artifact_sha256,
      modules_json,
      dependency_ids_json,
      state,
      sender_address,
      transaction_bytes_b64,
      signature,
      tx_digest,
      package_id,
      coin_type,
      prepared_at,
      submitted_at,
      confirmed_at,
      created_at,
      updated_at
    )
    VALUES (
      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
      'accepted',
      NULL, NULL, NULL, NULL,
      NULL, NULL, NULL, NULL, NULL,
      ?, ?
    )
  `).run(
    requested.publication_key,
    requested.chain,
    requested.network,
    requested.recipient_address,
    requested.module_name,
    requested.coin_struct_name,
    requested.source_sha256,
    requested.artifact_sha256,
    JSON.stringify(requested.modules),
    JSON.stringify(requested.dependency_ids),
    now,
    now,
  );

  res.status(201).json({
    created: true,
    publication: publicCreatorPublication(
      getCreatorPublication(
        requested.publication_key,
      )!
    ),
  });
});

app.post(
  "/v1/creator-publications/:publicationKey/prepare",
  async (req, res) => {
    try {
      const publication =
        await prepareCreatorPublication(
          req.params.publicationKey,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator publication preparation failed",
      });
    }
  },
);

app.post(
  "/v1/creator-publications/:publicationKey/submit",
  async (req, res) => {
    try {
      const publication =
        await submitPreparedCreatorPublication(
          req.params.publicationKey,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator publication submission failed",
      });
    }
  },
);

app.post(
  "/v1/creator-publications/:publicationKey/reconcile",
  async (req, res) => {
    try {
      const publication =
        await reconcileCreatorPublication(
          req.params.publicationKey,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator publication reconciliation failed",
      });
    }
  },
);

app.post(
  "/v1/creator-publications/:publicationKey/recover",
  async (req, res) => {
    try {
      const txDigest =
        typeof req.body?.tx_digest === "string"
          ? req.body.tx_digest.trim()
          : "";

      const publication =
        await recoverCreatorPublication(
          req.params.publicationKey,
          txDigest,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator publication recovery failed",
      });
    }
  },
);

app.post(
  "/v1/creator-publications/:publicationKey/register",
  async (req, res) => {
    try {
      const publication =
        await registerCreatorCurrency(
          req.params.publicationKey,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator Currency registration failed",
      });
    }
  },
);


app.post(
  "/v1/creator-publications/:publicationKey/metadata-cap/recover",
  async (req, res) => {
    try {
      const publication =
        await recoverCreatorMetadataCap(
          req.params.publicationKey,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator MetadataCap recovery failed",
      });
    }
  },
);


app.post(
  "/v1/creator-publications/:publicationKey/registration/recover",
  async (req, res) => {
    try {
      const txDigest =
        typeof req.body?.tx_digest === "string"
          ? req.body.tx_digest.trim()
          : "";

      const publication =
        await recoverCreatorCurrencyRegistration(
          req.params.publicationKey,
          txDigest,
        );

      res.json({
        publication:
          publicCreatorPublication(publication),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator Currency registration recovery failed",
      });
    }
  },
);


app.get(
  "/v1/creator-publications/:publicationKey/coin-image",
  (req, res) => {
    const publication =
      getCreatorPublication(
        req.params.publicationKey,
      );

    if (!publication) {
      res.status(404).json({
        error: "creator publication not found",
      });
      return;
    }

    if (
      publication.state !== "confirmed" ||
      !publication.coin_type
    ) {
      res.status(400).json({
        error:
          "creator publication is not confirmed",
      });
      return;
    }

    if (
      !publication.registered_currency_object_id ||
      !publication.registration_tx_digest ||
      !publication.registered_at
    ) {
      res.status(400).json({
        error:
          "creator Currency is not registered",
      });
      return;
    }

    const changeCount =
      publication.coin_image_change_count;

    res.json({
      coin_image: {
        publication_key:
          publication.publication_key,
        coin_type:
          publication.coin_type,
        registered_currency_object_id:
          publication.registered_currency_object_id,
        coin_image_url:
          publication.coin_image_url,
        coin_image_tx_digest:
          publication.coin_image_tx_digest,
        coin_image_set_at:
          publication.coin_image_set_at,
        coin_image_change_count:
          changeCount,
        first_image_free:
          changeCount === 0,
        next_price_usd:
          changeCount === 0
            ? "0.00"
            : "5.00",
      },
    });
  },
);


app.get(
  "/v1/creator-publications/:publicationKey/supply",
  async (req, res) => {
    try {
      const supply =
        await getCreatorPublicationSupply(
          req.params.publicationKey,
        );

      res.json({
        supply,
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "creator publication supply lookup failed",
      });
    }
  },
);

app.get(
  "/v1/creator-publications/:publicationKey",
  (req, res) => {
    const publication =
      getCreatorPublication(
        req.params.publicationKey,
      );

    if (!publication) {
      res.status(404).json({
        error: "creator publication not found",
      });
      return;
    }

    res.json({
      publication:
        publicCreatorPublication(publication),
    });
  },
);


app.post(
  "/v1/testnet/probes/:submissionKey/prepare",
  async (req, res) => {
    try {
      const delivery =
        await prepareTestnetProbe(
          req.params.submissionKey,
        );

      res.json({
        delivery: publicDelivery(delivery),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "testnet preparation failed",
      });
    }
  },
);


app.post(
  "/v1/testnet/probes/:submissionKey/submit",
  async (req, res) => {
    try {
      const delivery =
        await submitPreparedTestnetProbe(
          req.params.submissionKey,
        );

      res.json({
        delivery: publicDelivery(delivery),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "testnet submission failed",
      });
    }
  },
);


app.post(
  "/v1/testnet/probes/:submissionKey/reconcile",
  async (req, res) => {
    try {
      const delivery =
        await reconcileTestnetProbe(
          req.params.submissionKey,
        );

      res.json({
        delivery: publicDelivery(delivery),
      });
    } catch (error) {
      res.status(400).json({
        error:
          error instanceof Error
            ? error.message
            : "testnet reconciliation failed",
      });
    }
  },
);


app.listen(PORT, "0.0.0.0", () => {
  console.log(`fanz-sui mock adapter listening on ${PORT}`);
});
