# Kameleo Proxy Integration

How to add a proxy (e.g. BrightData) to Kameleo + Playwright price extraction.

## Kameleo Proxy Setup (Official Docs)

Proxy is configured when **creating the profile**, not when starting Playwright.

### Python (from Kameleo Developer Center)

```python
from kameleo.local_api_client.models import CreateProfileRequest, ProxyChoice, Server

profile = client.profile.create_profile(CreateProfileRequest(
    fingerprint_id=fps[0].id,
    name='proxy example',
    proxy=ProxyChoice(
        value='http',   # or 'https', 'socks5', 'ssh'
        extra=Server(
            host='brd.superproxy.io',    # proxy host
            port=33335,                   # proxy port
            id='brd-customer-XXX-zone-YYY',   # username (id)
            secret='password'             # password (secret)
        )
    )
))
```

### Server Parameters

| Field   | Meaning    | Example                         |
|---------|------------|---------------------------------|
| `host`  | Proxy host | `brd.superproxy.io`             |
| `port`  | Proxy port | `33335`                         |
| `id`    | Username   | `brd-customer-XXX-zone-YYY`     |
| `secret`| Password   | Your zone password              |

### BrightData Format

Parse from `BRIGHTDATA_PROXY`:

```
http://brd-customer-<cid>-zone-<zone>:<password>@brd.superproxy.io:33335
```

- host: `brd.superproxy.io`
- port: `33335`
- id: `brd-customer-<cid>-zone-<zone>`
- secret: `<password>`

### Supported Proxy Types

`ProxyChoice.value`: `'http'`, `'https'`, `'socks5'`, `'ssh'`

BrightData datacenter proxies use **HTTP**.

## Key Points from Kameleo Docs

1. **Proxy is tested before launch** – If Kameleo cannot reach the internet or get external IP through the proxy, you get:
   ```
   code=503 error={'global': ['Failed to determine external IP address for the profile, check Proxy settings.']}
   ```

2. **Match proxy country with fingerprint** – Best practice: use a proxy in the same country as the fingerprint locale.

3. **Do not configure proxy via Playwright** – Set it in Kameleo `CreateProfileRequest`; do not pass `proxy=` to Playwright.

## Troubleshooting "Failed to determine external IP"

- **Verify BrightData zone** – Ensure the zone is a **Datacenter** (or Residential) proxy zone that supports HTTP. SERP/Unlocker zones are different products.
- **Test proxy directly** – `curl "http://lumtest.com/myip.json" --proxy brd.superproxy.io:33335 --proxy-user user:pass` should return JSON with `ip`.
- **Credentials** – Confirm username/password from BrightData dashboard. Zone name is case-sensitive.
- **Fallback** – Use `--no-proxy` (or omit proxy) to run Kameleo without proxy for testing; some sites may block non-proxied traffic.

## Optional: WebRTC IP Leak Prevention

For Chroma (Chrome), add when starting the profile:

```python
Preference(key="webrtc.ip_handling_policy", value="disable_non_proxied_udp")
```

Some proxy providers don't support UDP; this keeps WebRTC over TCP through the proxy.

## References

- [Using proxy servers | Kameleo Developer Center](https://developer.kameleo.io/tutorials/using-proxy-servers/)
- [Supported Proxy Connection Strings | Kameleo KB](https://help.kameleo.io/article/53-supported-proxy-connection-strings)
- [BrightData: Send your first request](https://docs.brightdata.com/proxy-networks/data-center/send-your-first-request)
