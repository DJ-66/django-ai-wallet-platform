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
    prepared_at TEXT,
    submitted_at TEXT,
    confirmed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );
`);

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
    module_name: row.module_name,
    coin_struct_name: row.coin_struct_name,
    source_sha256: row.source_sha256,
    artifact_sha256: row.artifact_sha256,
    state: row.state,
    sender_address: row.sender_address,
    tx_digest: row.tx_digest,
    package_id: row.package_id,
    coin_type: row.coin_type,
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
  if (!TESTNET_PREPARE_ENABLED) {
    throw new Error(
      "Testnet transaction preparation is disabled"
    );
  }

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

  const keypair = requireTestnetSigner();
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

  tx.transferObjects(
    [upgradeCap],
    sender,
  );

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
      ?, ?, ?, ?, ?, ?, ?, ?,
      'accepted',
      NULL, NULL, NULL, NULL,
      NULL, NULL, NULL, NULL, NULL,
      ?, ?
    )
  `).run(
    requested.publication_key,
    requested.chain,
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
