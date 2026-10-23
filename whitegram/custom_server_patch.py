#!/usr/bin/env python3
"""Patch Telegram-iOS sources to connect directly to gramsrv private MTProto server."""

import sys
import re
from pathlib import Path

SERVER_IP = "2.26.3.112"
SERVER_PORT = 2398
SERVER_DC_ID = 2

SERVER_RSA_KEY_PEM = (
    "-----BEGIN RSA PUBLIC KEY-----\\n"
    "MIIBCgKCAQEAuK1sDwtQy/4XQyb2iRYkADgutpl7CT23RbTyF7Riz3X6w4flpk2B\\n"
    "yGFDzVgWHZciXevueP7f08F3hGhJWHeMJNPNMcdLia1L1MItYiqPrXU1Rp/MFpjl\\n"
    "yDOsQUZB62Xidsat67GjGO+UhjiEt4ef0S8h1xSO1iFgg/FWtl3XMsVrBTvaiHkh\\n"
    "gEf1NhAbgKiPHv4t2f0/PmMDjrMFlQlXet8nd6ASrW6vshlm7fTOfX1/HAIW3eoe\\n"
    "iZ7zwQgBtC4I9YWq2akA9TlSnC3P0gXnPj/wbiGVTFI+ekaG1koeWtXJKa/Nh0n9\\n"
    "O3+gwetGkI4LhpluYosOvVgY53SKSd6r3wIDAQAB\\n"
    "-----END RSA PUBLIC KEY-----"
)


def patch_network_swift(root: Path):
    path = root / "submodules" / "TelegramCore" / "Sources" / "Network" / "Network.swift"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    text = path.read_text(encoding="utf-8")

    if SERVER_IP in text and f"port: {SERVER_PORT}" in text:
        print(f"[OK] Already patched {path} with {SERVER_IP}:{SERVER_PORT}")
        return

    # 1. Replace seedAddressList definition
    seed_pattern = re.compile(
        r"let seedAddressList:\s*\[Int:\s*\[String\]\].*?for \(id, ips\) in seedAddressList \{",
        re.DOTALL
    )
    replacement = f"""let seedAddressList: [Int: [String]] = [
                1: ["{SERVER_IP}"],
                2: ["{SERVER_IP}"],
                3: ["{SERVER_IP}"],
                4: ["{SERVER_IP}"],
                5: ["{SERVER_IP}"]
            ]
            
            for (id, ips) in seedAddressList {{"""

    new_text, count = seed_pattern.subn(replacement, text)
    if count == 0 and SERVER_IP not in text:
        raise ValueError("Could not find seedAddressList in Network.swift")

    # 2. Replace port: 443 with custom server port
    port_pattern = re.compile(r"port:\s*443")
    new_text, port_count = port_pattern.subn(f"port: {SERVER_PORT}", new_text)
    if port_count == 0 and f"port: {SERVER_PORT}" not in new_text:
        raise ValueError("Could not find port: 443 in Network.swift")

    path.write_text(new_text, encoding="utf-8")
    print(f"[OK] Patched {path} with {SERVER_IP}:{SERVER_PORT}")


def patch_account_swift(root: Path):
    path = root / "submodules" / "TelegramCore" / "Sources" / "Account" / "Account.swift"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    text = path.read_text(encoding="utf-8")

    if f"let initialDatacenterId: Int = {SERVER_DC_ID}" in text and "#if DEBUG" not in text:
        print(f"[OK] Already patched {path} to default DC {SERVER_DC_ID}")
        return

    # Force initial datacenter ID to SERVER_DC_ID
    target = """#if DEBUG
                        let initialDatacenterId: Int = 1
                        #else
                        let initialDatacenterId: Int = 2
                        #endif"""
    replacement = f"""let initialDatacenterId: Int = {SERVER_DC_ID}"""

    if target in text:
        new_text = text.replace(target, replacement)
        path.write_text(new_text, encoding="utf-8")
        print(f"[OK] Patched {path} to default DC {SERVER_DC_ID}")
    else:
        new_text, count = re.subn(
            r"let initialDatacenterId:\s*Int\s*=\s*\d+",
            f"let initialDatacenterId: Int = {SERVER_DC_ID}",
            text
        )
        if count > 0:
            path.write_text(new_text, encoding="utf-8")
            print(f"[OK] Regex patched {path} to default DC {SERVER_DC_ID}")
        else:
            print(f"[WARN] initialDatacenterId anchor not found in {path}")


def patch_datacenter_auth_message_service(root: Path):
    path = root / "submodules" / "MtProtoKit" / "Sources" / "MTDatacenterAuthMessageService.m"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    text = path.read_text(encoding="utf-8")

    if "AuK1sDwtQy" in text:
        print(f"[OK] Already patched {path} with custom RSA key")
        return

    func_pattern = re.compile(
        r"static NSArray<MTDatacenterAuthPublicKey \*> \*defaultPublicKeys\(bool isProduction\) \{.*?\n\}",
        re.DOTALL
    )

    replacement = f"""static NSArray<MTDatacenterAuthPublicKey *> *defaultPublicKeys(bool isProduction) {{
    static NSArray<MTDatacenterAuthPublicKey *> *customKeys = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{{
        customKeys = @[
            [[MTDatacenterAuthPublicKey alloc] initWithPublicKey:@"{SERVER_RSA_KEY_PEM}"]
        ];
    }});
    return customKeys;
}}"""

    new_text, count = func_pattern.subn(replacement, text)
    if count == 0:
        raise ValueError("Could not find defaultPublicKeys in MTDatacenterAuthMessageService.m")

    path.write_text(new_text, encoding="utf-8")
    print(f"[OK] Patched {path} with custom RSA public key")


def patch_discover_connection_signals(root: Path):
    path = root / "submodules" / "MtProtoKit" / "Sources" / "MTDiscoverConnectionSignals.m"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    text = path.read_text(encoding="utf-8")

    if "return @[];" in text and "@[@80, @5222]" not in text:
        print(f"[OK] Already patched {path} to disable ports 80/5222 fallback")
        return

    target = "return @[@80, @5222];"
    if target in text:
        new_text = text.replace(target, "return @[];")
        path.write_text(new_text, encoding="utf-8")
        print(f"[OK] Patched {path} to disable ports 80/5222 fallback")
    else:
        print(f"[WARN] alternatePorts anchor not found in {path}")


def patch_backup_address_signals(root: Path):
    path = root / "submodules" / "MtProtoKit" / "Sources" / "MTBackupAddressSignals.m"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}")
    text = path.read_text(encoding="utf-8")

    if "return [MTSignal complete];" in text:
        print(f"[OK] Already patched {path} to return [MTSignal complete]")
        return

    func_pattern = re.compile(
        r"(\+ \(MTSignal \*[^\)]*\)fetchBackupIps:[^\{]*\{)"
    )

    new_text, count = func_pattern.subn(r"\1\n    return [MTSignal complete];", text)
    if count > 0:
        path.write_text(new_text, encoding="utf-8")
        print(f"[OK] Patched {path} to return [MTSignal complete]")
    else:
        print(f"[WARN] fetchBackupIps anchor not found in {path}")


def apply_custom_server_patches(root_dir: str):
    root = Path(root_dir).resolve()
    print(f"Applying custom server patches to {root}...")
    patch_network_swift(root)
    patch_account_swift(root)
    patch_datacenter_auth_message_service(root)
    patch_discover_connection_signals(root)
    patch_backup_address_signals(root)
    print("All custom server patches applied successfully!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <telegram-ios-root-path>")
        sys.exit(1)
    apply_custom_server_patches(sys.argv[1])
