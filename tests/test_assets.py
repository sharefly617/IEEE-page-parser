from src.assets import _safe_remote_host, convert_gif_assets, safe_filename


def test_safe_filename_is_local_and_stable():
    name = safe_filename("https://example.com/a/b figure.png")
    assert "/" not in name and "\\" not in name
    assert name.endswith(".png")


def test_private_asset_hosts_are_rejected():
    assert not _safe_remote_host("127.0.0.1")
    assert _safe_remote_host("cdn.example.com")


def test_gif_assets_are_converted_to_png(tmp_path):
    from PIL import Image
    gif = tmp_path / "figure.gif"
    Image.new("RGB", (2, 2), "white").save(gif, format="GIF")
    mapping = {"/figure.gif": "assets/figure.gif"}
    result = convert_gif_assets(tmp_path, mapping)
    assert result["/figure.gif"] == "assets/figure.png"
    assert (tmp_path / "figure.png").exists()
