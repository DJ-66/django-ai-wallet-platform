#!/bin/sh

docker exec -i fanz-sui-sui-1 node - <<'NODE'
try {
  const response = await fetch(
    "http://127.0.0.1:3000/v1/mainnet/treasury/sweep",
    {
      method: "POST",
      headers: {
        Authorization:
          `Bearer ${process.env.FANZ_SUI_API_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: "{}",
    },
  );

  const body = await response.text();

  console.log(body);

  if (!response.ok) {
    console.error(
      `Treasury sweep HTTP ${response.status}`
    );
    process.exitCode = 1;
  }
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
NODE

exit $?
