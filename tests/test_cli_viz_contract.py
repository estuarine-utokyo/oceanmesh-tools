from pathlib import Path

import types

from oceanmesh_tools.cli import build_parser, cmd_viz


def test_cli_viz_kwargs_filtered(monkeypatch, tmp_path: Path):
    # Prepare args with many flags, including those that plot_mesh may not accept
    fort14 = Path('tests/fixtures/tiny.fort14')
    outdir = tmp_path

    # Monkeypatch viz.plot_mesh to accept only minimal kwargs (force filtering)
    import oceanmesh_tools.plot.viz as viz

    called = {}

    def fake_plot_mesh(f14_path: Path, outdir: Path):
        # Ensure types are Path and file exists
        assert isinstance(f14_path, Path)
        assert f14_path.exists()
        called['ok'] = True
        return outdir / 'mesh.png'

    monkeypatch.setattr(viz, 'plot_mesh', fake_plot_mesh)

    parser = build_parser()
    args = parser.parse_args([
        'viz',
        '--fort14', str(fort14),
        '--out', str(outdir),
        '--coast-include-holes',
        '--coast-clip-to-domain',
        '--coast-clip-eps', '1e-6',
        '--coast-subtract-near-ob',
        '--coast-subtract-tol', '0.002',
        '--mesh-add-coastline',
        '--mesh-add-open-boundaries',
        '--coast-skip-near-openbnd',
        '--coast-skip-tol', '0.01',
    ])

    # Should not raise due to unexpected kwargs
    rc = cmd_viz(args)
    assert rc == 0
    assert called.get('ok')

