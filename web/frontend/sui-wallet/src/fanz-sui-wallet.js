import {
  getWallets,
  StandardConnect,
  SuiSignAndExecuteTransaction,
  SUI_MAINNET_CHAIN,
  signAndExecuteTransaction,
} from "@mysten/wallet-standard";

import {
  Transaction,
} from "@mysten/sui/transactions";

const registry = getWallets();

function walletSummary(wallet) {
  return {
    name: wallet.name,
    version: wallet.version,
    chains: wallet.chains || [],
    accounts: (wallet.accounts || []).map((account) => ({
      address: account.address,
      chains: account.chains || [],
      features: account.features || [],
    })),
    features: Object.keys(wallet.features || {}),
    canConnect:
      Boolean(wallet.features?.[StandardConnect]),
    canSignAndExecute:
      Boolean(
        wallet.features?.[
          SuiSignAndExecuteTransaction
        ]
      ),
  };
}

function logWallets(label) {
  const wallets = registry.get();

  console.log(
    `[FANZ Sui] ${label}:`,
    wallets.map(walletSummary),
  );

  return wallets;
}

logWallets("wallets at startup");

registry.on("register", (...wallets) => {
  console.log(
    "[FANZ Sui] wallet registered:",
    wallets.map(walletSummary),
  );

  logWallets("wallets after registration");
});

registry.on("unregister", (...wallets) => {
  console.log(
    "[FANZ Sui] wallet unregistered:",
    wallets.map((wallet) => wallet.name),
  );
});

window.FANZSuiWallet = {
  wallets() {
    return registry.get().map(walletSummary);
  },

  rawWallets() {
    return registry.get();
  },

  async connect(walletName = null) {
    const wallets = registry.get();

    const wallet =
      walletName
        ? wallets.find(
            (candidate) =>
              candidate.name === walletName &&
              (candidate.chains || []).includes(
                SUI_MAINNET_CHAIN
              ) &&
              Boolean(
                candidate.features?.[
                  StandardConnect
                ]
              ) &&
              Boolean(
                candidate.features?.[
                  SuiSignAndExecuteTransaction
                ]
              )
          )
        : wallets.find(
            (candidate) =>
              (candidate.chains || []).includes(
                SUI_MAINNET_CHAIN
              ) &&
              Boolean(
                candidate.features?.[
                  StandardConnect
                ]
              ) &&
              Boolean(
                candidate.features?.[
                  SuiSignAndExecuteTransaction
                ]
              )
          );

    if (!wallet) {
      throw new Error(
        "No connectable Sui wallet found."
      );
    }

    const connectFeature =
      wallet.features?.[
        StandardConnect
      ];

    if (!connectFeature) {
      throw new Error(
        `${wallet.name} does not support wallet connection.`
      );
    }

    const result =
      await connectFeature.connect();

    const accounts =
      result?.accounts ||
      wallet.accounts ||
      [];

    const mainnetAccounts =
      accounts.filter(
        (account) =>
          (account.chains || []).includes(
            SUI_MAINNET_CHAIN
          )
      );

    console.log(
      "[FANZ Sui] connected:",
      {
        wallet: wallet.name,
        accounts:
          mainnetAccounts.map(
            (account) => account.address
          ),
      },
    );

    if (!mainnetAccounts.length) {
      throw new Error(
        `${wallet.name} connected, but no Sui Mainnet account is available.`
      );
    }

    return {
      wallet: wallet.name,
      accounts:
        mainnetAccounts.map(
          (account) => account.address
        ),
    };
  },

  async paySui({
    walletName = null,
    recipientAddress,
    amountMist,
  }) {
    const wallets = registry.get();

    const compatibleWallets =
      wallets.filter(
        (candidate) =>
          (candidate.chains || []).includes(
            SUI_MAINNET_CHAIN
          ) &&
          Boolean(
            candidate.features?.[
              StandardConnect
            ]
          ) &&
          Boolean(
            candidate.features?.[
              SuiSignAndExecuteTransaction
            ]
          )
      );

    let wallet = null;

    if (walletName) {
      wallet = compatibleWallets.find(
        (candidate) =>
          candidate.name === walletName
      );
    } else {
      wallet =
        compatibleWallets.find(
          (candidate) =>
            candidate.name === "Slush"
        ) ||
        compatibleWallets.find(
          (candidate) =>
            candidate.name === "Suiet"
        ) ||
        compatibleWallets[0];
    }

    if (!wallet) {
      throw new Error(
        `Sui wallet ${walletName || ""} is not available.`
      );
    }

    if (!wallet.accounts?.length) {
      await wallet.features[
        StandardConnect
      ].connect();
    }

    const account =
      (wallet.accounts || []).find(
        (candidate) =>
          (candidate.chains || []).includes(
            SUI_MAINNET_CHAIN
          )
      );

    if (!account) {
      throw new Error(
        `${wallet.name} has no Sui Mainnet account available.`
      );
    }

    const recipient =
      String(recipientAddress || "").trim();

    if (!recipient) {
      throw new Error(
        "SUI payment recipient is missing."
      );
    }

    let amount;

    try {
      amount = BigInt(
        String(amountMist || "").trim()
      );
    } catch {
      throw new Error(
        "SUI payment amount is invalid."
      );
    }

    if (amount <= 0n) {
      throw new Error(
        "SUI payment amount must be greater than zero."
      );
    }

    const transaction = new Transaction();

    const [paymentCoin] =
      transaction.splitCoins(
        transaction.gas,
        [transaction.pure.u64(amount)]
      );

    transaction.transferObjects(
      [paymentCoin],
      transaction.pure.address(recipient)
    );

    const result =
      await signAndExecuteTransaction(
        wallet,
        {
          account,
          chain: SUI_MAINNET_CHAIN,
          transaction,
        },
      );

    if (!result?.digest) {
      throw new Error(
        "Wallet returned no transaction digest."
      );
    }

    console.log(
      "[FANZ Sui] payment published:",
      {
        wallet: wallet.name,
        account: account.address,
        recipient,
        amountMist: amount.toString(),
        digest: result.digest,
      },
    );

    return {
      wallet: wallet.name,
      account: account.address,
      recipient,
      amountMist: amount.toString(),
      digest: result.digest,
    };
  },

  async signAndPublish({
    walletName = null,
    ownerAddress,
    transactionBytesB64,
  }) {
    const wallets = registry.get();

    const compatibleWallets =
      wallets.filter(
        (candidate) =>
          (candidate.chains || []).includes(
            SUI_MAINNET_CHAIN
          ) &&
          Boolean(
            candidate.features?.[
              StandardConnect
            ]
          ) &&
          Boolean(
            candidate.features?.[
              SuiSignAndExecuteTransaction
            ]
          )
      );

    let wallet = null;

    if (walletName) {
      wallet = compatibleWallets.find(
        (candidate) =>
          candidate.name === walletName
      );
    } else {
      wallet =
        compatibleWallets.find(
          (candidate) =>
            candidate.name === "Slush"
        ) ||
        compatibleWallets.find(
          (candidate) =>
            candidate.name === "Suiet"
        ) ||
        compatibleWallets[0];
    }

    if (!wallet) {
      throw new Error(
        `Sui wallet ${walletName} is not available.`
      );
    }

    if (!wallet.accounts?.length) {
      await wallet.features[
        StandardConnect
      ].connect();
    }

    const expected =
      String(ownerAddress || "")
        .trim()
        .toLowerCase();

    const account =
      (wallet.accounts || []).find(
        (candidate) =>
          String(candidate.address || "")
            .toLowerCase() === expected &&
          (candidate.chains || []).includes(
            SUI_MAINNET_CHAIN
          )
      );

    if (!account) {
      throw new Error(
        `Connected ${wallet.name} account does not match the prepared owner ${expected}.`
      );
    }

    const transaction =
      Transaction.from(
        String(transactionBytesB64 || "")
          .trim()
      );

    const result =
      await signAndExecuteTransaction(
        wallet,
        {
          account,
          chain:
            SUI_MAINNET_CHAIN,
          transaction,
        },
      );

    if (!result?.digest) {
      throw new Error(
        "Wallet returned no transaction digest."
      );
    }

    console.log(
      "[FANZ Sui] transaction published:",
      {
        wallet: wallet.name,
        account: account.address,
        digest: result.digest,
      },
    );

    return {
      wallet:
        wallet.name,
      account:
        account.address,
      digest:
        result.digest,
    };
  },

  mainnetChain:
    SUI_MAINNET_CHAIN,
};

console.log(
  "[FANZ Sui] wallet bridge ready",
);
