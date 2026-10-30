"""不依赖本机Docker，从Docker Hub下载官方镜像并生成docker load归档。"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.parse
import urllib.request


ACCEPT = ", ".join(("application/vnd.oci.image.index.v1+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.docker.distribution.manifest.v2+json"))


def sha_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Registry:
    def __init__(self, repository, root):
        self.repository, self.root = repository, root
        query = urllib.parse.urlencode({"service": "registry.docker.io",
                                       "scope": f"repository:{repository}:pull"})
        with urllib.request.urlopen("https://auth.docker.io/token?" + query, timeout=30) as response:
            self.token = json.load(response)["token"]

    def request(self, path):
        request = urllib.request.Request(
            f"https://registry-1.docker.io/v2/{self.repository}/{path}",
            headers={"Authorization": "Bearer " + self.token, "Accept": ACCEPT})
        return urllib.request.urlopen(request, timeout=90)

    def manifest(self, reference):
        with self.request("manifests/" + reference) as response:
            content = response.read()
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if reference.startswith("sha256:") and digest != reference:
            raise ValueError("镜像清单摘要不一致")
        manifest = json.loads(content)
        if "manifests" in manifest:
            target = next(item for item in manifest["manifests"]
                          if item.get("platform", {}).get("os") == "linux"
                          and item["platform"].get("architecture") == "amd64")
            return self.manifest(target["digest"])
        return manifest, digest

    def blob(self, digest):
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError("镜像内容摘要无效")
        target = self.root / "blobs" / digest.split(":")[1]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and sha_file(target) == digest[7:]:
            return target
        staged = target.with_suffix(".download")
        with self.request("blobs/" + digest) as response, staged.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        if sha_file(staged) != digest[7:]:
            raise ValueError("镜像内容摘要不一致")
        staged.replace(target)
        return target


def collect_image(image, root):
    repository, tag = image.rsplit(":", 1)
    if repository not in {"python", "postgres", "nginx", "certbot/certbot"}:
        raise ValueError("仅接受本项目使用的官方镜像")
    registry = Registry(repository if "/" in repository else "library/" + repository, root)
    manifest, digest = registry.manifest(tag)
    config_path = registry.blob(manifest["config"]["digest"])
    config = json.loads(config_path.read_bytes())
    if (config.get("os"), config.get("architecture")) != ("linux", "amd64"):
        raise ValueError("镜像平台不符合服务器")
    files = {config_path.name + ".json": config_path}
    layers = []
    for descriptor, diff_id in zip(manifest["layers"], config["rootfs"]["diff_ids"], strict=True):
        compressed = registry.blob(descriptor["digest"])
        layer = root / "layers" / (diff_id[7:] + ".tar")
        layer.parent.mkdir(parents=True, exist_ok=True)
        if not layer.is_file() or sha_file(layer) != diff_id[7:]:
            media_type = descriptor["mediaType"]
            if not (media_type.endswith("gzip") or media_type.endswith(".tar")):
                raise ValueError("暂不支持该镜像层压缩格式")
            opener = gzip.open if media_type.endswith("gzip") else open
            with opener(compressed, "rb") as source, layer.open("wb") as destination:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
            if sha_file(layer) != diff_id[7:]:
                raise ValueError("解压后的镜像层摘要不一致")
        name = diff_id[7:] + "/layer.tar"
        files[name] = layer
        layers.append(name)
    return {"Config": config_path.name + ".json", "RepoTags": [image], "Layers": layers}, files, digest


def build(images, root):
    root.mkdir(parents=True, exist_ok=True)
    manifests, files, records = [], {}, []
    for image in images:
        manifest, image_files, digest = collect_image(image, root)
        manifests.append(manifest)
        files.update(image_files)
        records.append({"image": image, "platform": "linux/amd64", "manifest_digest": digest})
        print(json.dumps({"image": image, "download_verified": True}), flush=True)
    output = root / "base-images.tar.gz"
    if output.exists():
        raise ValueError("镜像归档已存在，请另选输出目录")
    with output.open("xb") as stream, gzip.GzipFile(fileobj=stream, mode="wb", compresslevel=1, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for name, path in sorted(files.items()):
                info = tarfile.TarInfo(name)
                info.size, info.mode = path.stat().st_size, 0o644
                with path.open("rb") as source:
                    archive.addfile(info, source)
            content = json.dumps(manifests).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size, info.mode = len(content), 0o644
            archive.addfile(info, io.BytesIO(content))
    result = {"images": records, "archive": output.name, "bytes": output.stat().st_size,
              "sha256": sha_file(output)}
    (root / "images.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--image", action="append", required=True)
    arguments = parser.parse_args()
    build(arguments.image, arguments.root)
