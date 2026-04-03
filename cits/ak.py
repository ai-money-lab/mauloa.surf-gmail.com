import os
import subprocess

key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFXjRl8inYMa4q/Idwl4Kk6njtciiRReq44y7iKBYe3d hirokmiyao@mac"

# Both locations
paths = [
    os.path.expanduser("~") + "/.ssh/authorized_keys",
    "C:/ProgramData/ssh/administrators_authorized_keys"
]

for path in paths:
    # Create dir if needed
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    
    # Add key if not already present
    content = ""
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
    
    if key not in content:
        with open(path, "a") as f:
            f.write("\n" + key + "\n")
        print(f"Key added to {path}")
    else:
        print(f"Key already in {path}")
    
    # Fix ACL - remove inheritance, grant only Administrators and SYSTEM
    subprocess.run(["icacls", path, "/inheritance:r", "/grant", "Administrators:F", "/grant", "SYSTEM:F"], capture_output=True)
    print(f"ACL fixed for {path}")

# Restart sshd
subprocess.run(["powershell", "-Command", "Restart-Service sshd"], capture_output=True)
print("sshd restarted")
print("ALL DONE")
