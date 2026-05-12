import json

from PIL import Image

from scripts.generate_spec_snippets import generate_spec_snippets


def test_generate_spec_snippets_writes_specific_assets_and_index(tmp_path):
    source_dir = tmp_path / "spec-images"
    output_dir = tmp_path / "spec-snippets"
    index_path = tmp_path / "spec-assets.json"
    source_dir.mkdir()
    output_dir.mkdir()
    Image.new("RGB", (3840, 2032), color=(255, 255, 255)).save(source_dir / "buttons.png")
    Image.new("RGB", (1912, 1106), color=(255, 255, 255)).save(source_dir / "tags.png")
    Image.new("RGB", (320, 120), color=(107, 54, 250)).save(
        output_dir / "color-ai-main-color.png"
    )

    generate_spec_snippets(source_dir, output_dir, index_path)

    assert (output_dir / "color-ai-main-color.png").exists()
    assert (output_dir / "button-primary.png").exists()
    assert (output_dir / "tag-ai-capsule.png").exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    color_item = next(item for item in index["assets"] if item["id"] == "color-ai-main-color")
    assert color_item["url"] == "/spec-snippets/color-ai-main-color.png"
    assert "ai/ai-normal" in color_item["keywords"]
