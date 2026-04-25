from app.core.metrics import inc, render_prometheus


def test_prometheus_label_values_are_escaped():
    inc(
        "saferoute_test_metric_total",
        {
            "path": '/api/"quoted"\npath',
            "slash": r"a\b",
        },
    )

    metrics = render_prometheus()

    assert 'path="/api/\\"quoted\\"\\npath"' in metrics
    assert 'slash="a\\\\b"' in metrics

