import os
key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFXjRl8inYMa4q/Idwl4Kk6njtciiRReq44y7iKBYe3d hirokmiyao@mac"
path = os.path.expanduser("~") + "/.ssh/authorized_keys"
with open(path, "r") as f:
    content = f.read()
if key not in content:
    with open(path, "a") as f:
        f.write("\n" + key + "\n")
    print("Key added")
else:
    print("Key exists")
with open(path) as f:
    print(f.read())
