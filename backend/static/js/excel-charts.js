(function () {
  'use strict';

  var SERIES = [
    '#E8602C', '#1FA07A', '#7A5AF8', '#F5B301', '#E0407B', '#22A7D0',
    '#8AB833', '#B5179E', '#0E9594', '#D96704', '#5B6ABF', '#7F8C2A'
  ];

  var INK = '#404040';
  var RULE = '#D9D9D9';
  var AXIS = '#BFBFBF';
  var ROW_HEIGHT = 22;
  var TABLE_GAP = 6;
  var SWATCH = 9;
  var FONT = '11px "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif';
  var LABEL_GAP = 26;
  var MIN_COLUMN = 34;
  var MIN_BAND = 15;
  var MAX_COLUMNS = 14;
  var MAX_ROWS = 12;
  var MAX_LIST_ROWS = 16;
  var MAX_ROW_BANDS = 30;
  var MAX_VALUE_COLUMNS = 4;
  var VALUE_COLUMN = 78;
  var LIST_WIDTH = 460;

  function colour(index) {
    return SERIES[index % SERIES.length];
  }

  function labels(chart) {
    return chart.data.labels || [];
  }

  function datasets(chart) {
    return chart.data.datasets || [];
  }

  function categoryTitle(chart) {
    var options = chart.options.plugins && chart.options.plugins.excelDataTable;
    return (options && options.categoryTitle) || 'Category';
  }

  function mode(chart) {
    var type = chart.config.type;
    if (type === 'pie' || type === 'doughnut') return 'list';
    if (chart.options.indexAxis === 'y') return 'rows';
    return 'columns';
  }

  function wanted(chart) {
    var options = chart.options.plugins && chart.options.plugins.excelDataTable;
    if (!options || options.display === false) return false;
    var count = labels(chart).length;
    if (!count) return false;
    var shape = mode(chart);
    if (shape === 'columns') {
      return count <= MAX_COLUMNS && datasets(chart).length <= MAX_ROWS;
    }
    if (shape === 'rows') {
      return count <= MAX_ROW_BANDS && datasets(chart).length <= MAX_VALUE_COLUMNS;
    }
    return count <= MAX_LIST_ROWS;
  }

  function padding(chart) {
    var layout = chart.options.layout || (chart.options.layout = {});
    var pad = layout.padding;
    if (typeof pad === 'number') {
      pad = { top: pad, right: pad, bottom: pad, left: pad };
    } else {
      pad = Object.assign({ top: 0, right: 0, bottom: 0, left: 0 }, pad || {});
    }
    layout.padding = pad;
    return pad;
  }

  function clip(ctx, text, width) {
    var value = String(text == null ? '' : text).replace(/\s+/g, ' ');
    if (width <= 4) return '';
    if (ctx.measureText(value).width <= width) return value;
    while (value.length > 1 && ctx.measureText(value + '…').width > width) {
      value = value.slice(0, -1);
    }
    return value + '…';
  }

  function measure(chart, texts) {
    var ctx = chart.ctx;
    if (!ctx) return 0;
    var previous = ctx.font;
    ctx.font = FONT;
    var widest = 0;
    texts.forEach(function (text) {
      widest = Math.max(widest, ctx.measureText(String(text == null ? '' : text)).width);
    });
    ctx.font = previous;
    return Math.ceil(widest);
  }

  function readValue(point) {
    if (point && typeof point === 'object') {
      return point.y != null ? point.y : point.v;
    }
    return point;
  }

  function seriesColour(dataset, index) {
    var paint = Array.isArray(dataset.backgroundColor)
      ? dataset.backgroundColor[0]
      : dataset.backgroundColor;
    if (!paint || paint === 'transparent') paint = dataset.borderColor;
    return paint || colour(index);
  }

  function categoryColours(chart) {
    var rows = datasets(chart);
    if (rows.length !== 1) return null;
    var paint = rows[0].backgroundColor;
    return Array.isArray(paint) && paint.length > 1 ? paint : null;
  }

  function sliceColour(dataset, index) {
    var paint = dataset.backgroundColor;
    if (Array.isArray(paint)) return paint[index % paint.length];
    return paint || colour(index);
  }

  function grid(ctx, lines) {
    ctx.strokeStyle = RULE;
    ctx.beginPath();
    lines.forEach(function (line) {
      ctx.moveTo(line[0], line[1]);
      ctx.lineTo(line[2], line[3]);
    });
    ctx.stroke();
  }

  function frame(ctx, x, y, width, height) {
    ctx.strokeStyle = AXIS;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.rect(x + 0.5, y + 0.5, width - 1, height);
    ctx.stroke();
  }

  function drawColumns(chart) {
    var area = chart.chartArea;
    var names = labels(chart);
    var rows = datasets(chart);
    var columns = names.length;
    var bandWidth = (area.right - area.left) / columns;
    if (bandWidth < MIN_COLUMN) return;

    var ctx = chart.ctx;
    var left = 1;
    var split = area.left;
    var right = area.right;
    var top = area.bottom + TABLE_GAP;
    var height = (rows.length + 1) * ROW_HEIGHT;

    frame(ctx, left, top, right - left, height);

    var lines = [];
    for (var r = 1; r <= rows.length; r += 1) {
      lines.push([left, Math.round(top + r * ROW_HEIGHT) + 0.5,
                  right, Math.round(top + r * ROW_HEIGHT) + 0.5]);
    }
    for (var c = 0; c <= columns; c += 1) {
      var edge = Math.round(split + c * bandWidth) + 0.5;
      if (edge > left && edge < right) lines.push([edge, top, edge, top + height]);
    }
    grid(ctx, lines);

    var chips = categoryColours(chart);
    names.forEach(function (name, i) {
      var centre = split + (i + 0.5) * bandWidth;
      var room = bandWidth - 8;
      if (chips) {
        var text = clip(ctx, name, room - SWATCH - 6);
        var textWidth = ctx.measureText(text).width;
        ctx.fillStyle = chips[i % chips.length];
        ctx.fillRect(centre - textWidth / 2 - SWATCH - 4,
                     top + ROW_HEIGHT / 2 - SWATCH / 2, SWATCH, SWATCH);
        ctx.fillStyle = INK;
        ctx.textAlign = 'left';
        ctx.fillText(text, centre - textWidth / 2 + 2, top + ROW_HEIGHT / 2);
        return;
      }
      ctx.fillStyle = INK;
      ctx.textAlign = 'center';
      ctx.fillText(clip(ctx, name, room), centre, top + ROW_HEIGHT / 2);
    });

    rows.forEach(function (dataset, index) {
      var y = top + (index + 1.5) * ROW_HEIGHT;
      var textLeft = left + 6;
      if (!chips) {
        ctx.fillStyle = seriesColour(dataset, index);
        ctx.fillRect(left + 6, y - SWATCH / 2, SWATCH, SWATCH);
        textLeft = left + SWATCH + 12;
      }
      ctx.fillStyle = INK;
      ctx.textAlign = 'left';
      ctx.fillText(clip(ctx, dataset.label || '', split - textLeft - 10), textLeft, y);
      ctx.textAlign = 'center';
      (dataset.data || []).forEach(function (point, i) {
        if (i >= columns) return;
        var value = readValue(point);
        if (value == null || isNaN(value)) return;
        ctx.fillText(String(value), split + (i + 0.5) * bandWidth, y);
      });
    });
  }

  function drawRows(chart) {
    var area = chart.chartArea;
    var names = labels(chart);
    var series = datasets(chart);
    var count = names.length;
    var bandHeight = (area.bottom - area.top) / count;
    if (bandHeight < MIN_BAND) return;

    var ctx = chart.ctx;
    var left = 1;
    var right = area.left - TABLE_GAP;
    var valuesWidth = Math.min(series.length * VALUE_COLUMN, (right - left) * 0.6);
    var nameWidth = right - left - valuesWidth;
    if (nameWidth < 40) return;

    var top = area.top - ROW_HEIGHT;
    var height = ROW_HEIGHT + count * bandHeight;

    frame(ctx, left, top, right - left, height);

    var lines = [[left, Math.round(area.top) + 0.5, right, Math.round(area.top) + 0.5]];
    for (var r = 1; r < count; r += 1) {
      var y = Math.round(area.top + r * bandHeight) + 0.5;
      lines.push([left, y, right, y]);
    }
    for (var c = 0; c <= series.length; c += 1) {
      var edge = Math.round(left + nameWidth + c * (valuesWidth / series.length)) + 0.5;
      if (edge > left && edge < right) lines.push([edge, top, edge, top + height]);
    }
    grid(ctx, lines);

    ctx.fillStyle = INK;
    ctx.textAlign = 'left';
    ctx.fillText(clip(ctx, categoryTitle(chart), nameWidth - 12),
                 left + 6, top + ROW_HEIGHT / 2);

    var keyed = series.length > 1;
    series.forEach(function (dataset, index) {
      var columnWidth = valuesWidth / series.length;
      var columnLeft = left + nameWidth + index * columnWidth;
      var textLeft = columnLeft + 6;
      if (keyed) {
        ctx.fillStyle = seriesColour(dataset, index);
        ctx.fillRect(columnLeft + 5, top + ROW_HEIGHT / 2 - SWATCH / 2, SWATCH, SWATCH);
        textLeft = columnLeft + SWATCH + 10;
      }
      ctx.fillStyle = INK;
      ctx.textAlign = keyed ? 'left' : 'center';
      ctx.fillText(clip(ctx, dataset.label || '', columnWidth - (keyed ? SWATCH + 14 : 10)),
                   keyed ? textLeft : columnLeft + columnWidth / 2, top + ROW_HEIGHT / 2);
    });

    var chips = categoryColours(chart);
    names.forEach(function (name, i) {
      var centre = area.top + (i + 0.5) * bandHeight;
      var textLeft = left + 6;
      if (chips) {
        ctx.fillStyle = chips[i % chips.length];
        ctx.fillRect(left + 6, centre - SWATCH / 2, SWATCH, SWATCH);
        textLeft = left + SWATCH + 12;
      }
      ctx.fillStyle = INK;
      ctx.textAlign = 'left';
      ctx.fillText(clip(ctx, name, right - textLeft - valuesWidth - 8), textLeft, centre);
      ctx.textAlign = 'center';
      series.forEach(function (dataset, index) {
        var value = readValue((dataset.data || [])[i]);
        if (value == null || isNaN(value)) return;
        var columnWidth = valuesWidth / series.length;
        ctx.fillText(String(value),
                     left + nameWidth + (index + 0.5) * columnWidth, centre);
      });
    });
  }

  function drawList(chart) {
    var area = chart.chartArea;
    var names = labels(chart);
    var dataset = datasets(chart)[0];
    if (!dataset) return;

    var values = (dataset.data || []).map(readValue);
    var total = values.reduce(function (sum, value) {
      return sum + (typeof value === 'number' && !isNaN(value) ? value : 0);
    }, 0);

    var ctx = chart.ctx;
    var width = Math.max(LIST_WIDTH, Math.min(chart.width - 8, 680));
    var left = Math.round((chart.width - width) / 2);
    var right = left + width;
    var top = area.bottom + TABLE_GAP;
    var height = (names.length + 1) * ROW_HEIGHT;
    var valueColumn = 70;
    var shareColumn = 62;
    var nameWidth = width - valueColumn - shareColumn;
    if (nameWidth < 60) return;

    frame(ctx, left, top, width, height);

    var lines = [];
    for (var r = 1; r <= names.length; r += 1) {
      var y = Math.round(top + r * ROW_HEIGHT) + 0.5;
      lines.push([left, y, right, y]);
    }
    lines.push([Math.round(left + nameWidth) + 0.5, top,
                Math.round(left + nameWidth) + 0.5, top + height]);
    lines.push([Math.round(right - shareColumn) + 0.5, top,
                Math.round(right - shareColumn) + 0.5, top + height]);
    grid(ctx, lines);

    ctx.fillStyle = INK;
    ctx.textAlign = 'left';
    ctx.fillText(clip(ctx, categoryTitle(chart), nameWidth - 12),
                 left + 6, top + ROW_HEIGHT / 2);
    ctx.textAlign = 'center';
    ctx.fillText(clip(ctx, dataset.label || 'Value', valueColumn - 8),
                 left + nameWidth + valueColumn / 2, top + ROW_HEIGHT / 2);
    ctx.fillText('Share', right - shareColumn / 2, top + ROW_HEIGHT / 2);

    names.forEach(function (name, i) {
      var y = top + (i + 1.5) * ROW_HEIGHT;
      ctx.fillStyle = sliceColour(dataset, i);
      ctx.fillRect(left + 6, y - SWATCH / 2, SWATCH, SWATCH);
      ctx.fillStyle = INK;
      ctx.textAlign = 'left';
      ctx.fillText(clip(ctx, name, nameWidth - SWATCH - 20), left + SWATCH + 12, y);

      var value = values[i];
      if (value == null || isNaN(value)) return;
      ctx.textAlign = 'center';
      ctx.fillText(String(value), left + nameWidth + valueColumn / 2, y);
      ctx.fillText(total ? (value / total * 100).toFixed(1) + '%' : '—',
                   right - shareColumn / 2, y);
    });
  }

  var dataTable = {
    id: 'excelDataTable',

    beforeInit: function (chart) {
      if (!wanted(chart)) return;
      var plugins = chart.options.plugins || (chart.options.plugins = {});
      var legend = plugins.legend || (plugins.legend = {});
      legend.display = false;
    },

    beforeLayout: function (chart) {
      var pad = padding(chart);
      if (!chart.$excelBasePadding) {
        chart.$excelBasePadding = Object.assign({}, pad);
      }
      var base = chart.$excelBasePadding;
      pad.top = base.top;
      pad.right = base.right;
      pad.bottom = base.bottom;
      pad.left = base.left;
      if (!wanted(chart)) return;
      if (!chart.width || !chart.height) return;

      var widest = chart.width * 0.4;
      var tallest = chart.height * 0.5;
      var shape = mode(chart);

      if (shape === 'columns') {
        pad.bottom = Math.min(
          base.bottom + (datasets(chart).length + 1) * ROW_HEIGHT + TABLE_GAP, tallest);
        pad.left = Math.min(
          Math.max(base.left, measure(chart, datasets(chart).map(function (d) {
            return d.label || '';
          })) + LABEL_GAP), widest);
      } else if (shape === 'rows') {
        var names = measure(chart, labels(chart)) + 16;
        var values = datasets(chart).length * VALUE_COLUMN;
        var room = Math.max(120, chart.width * 0.34);
        pad.left = Math.min(
          Math.max(base.left, Math.min(names, room) + values + TABLE_GAP),
          Math.max(widest, chart.width * 0.55));
        pad.top = base.top + ROW_HEIGHT;
      } else {
        pad.bottom = Math.min(
          base.bottom + (labels(chart).length + 1) * ROW_HEIGHT + TABLE_GAP, tallest);
      }
    },

    afterDraw: function (chart) {
      if (!wanted(chart)) return;
      if (!chart.chartArea) return;

      var ctx = chart.ctx;
      ctx.save();
      ctx.font = FONT;
      ctx.textBaseline = 'middle';
      ctx.lineWidth = 1;

      var shape = mode(chart);
      if (shape === 'columns') drawColumns(chart);
      else if (shape === 'rows') drawRows(chart);
      else drawList(chart);

      ctx.restore();
    },
  };

  function axes(config) {
    var horizontal = config.indexAxis === 'y';
    var category = {
      grid: { display: false, drawBorder: true },
      border: { color: AXIS },
      ticks: { color: INK, display: config.showCategoryTicks !== false },
    };
    var value = {
      beginAtZero: true,
      grid: { color: RULE, drawBorder: false },
      border: { display: false },
      ticks: { color: INK, precision: 0, maxTicksLimit: 8 },
    };
    if (config.stepSize) value.ticks.stepSize = config.stepSize;
    return horizontal ? { x: value, y: category } : { x: category, y: value };
  }

  function options(config) {
    config = config || {};
    var pie = config.pie === true;
    var table = config.table === true;
    var horizontal = config.indexAxis === 'y';

    var base = {
      responsive: true,
      maintainAspectRatio: config.maintainAspectRatio !== false,
      animation: { duration: 220 },
      layout: { padding: { top: 4, right: 8, bottom: 2, left: 2 } },
      plugins: {
        title: {
          display: !!config.title,
          text: config.title || '',
          color: INK,
          font: { size: 15, weight: '400' },
          padding: { top: 2, bottom: 12 },
        },
        legend: {
          display: config.legend !== false,
          position: config.legendPosition || 'bottom',
          labels: {
            color: INK,
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: false,
            font: { size: 11 },
            generateLabels: config.generateLabels,
          },
        },
        tooltip: {
          backgroundColor: '#ffffff',
          titleColor: INK,
          bodyColor: INK,
          borderColor: AXIS,
          borderWidth: 1,
          displayColors: true,
          callbacks: config.tooltipCallbacks || {},
        },
        excelDataTable: {
          display: table,
          categoryTitle: config.categoryTitle || 'Category',
        },
      },
    };

    if (!base.plugins.legend.labels.generateLabels) {
      delete base.plugins.legend.labels.generateLabels;
    }

    if (!pie) {
      base.scales = axes(config);
      if (table) base.scales[horizontal ? 'y' : 'x'].ticks.display = false;
    }

    if (pie) base.aspectRatio = config.aspectRatio || 1.6;
    if (config.indexAxis) base.indexAxis = config.indexAxis;
    if (config.interaction) base.interaction = config.interaction;
    return base;
  }

  function bars(chartLabels, series) {
    var varied = series.length === 1 && (chartLabels || []).length > 1;
    return series.map(function (entry, index) {
      var paint = varied
        ? (chartLabels || []).map(function (_, i) { return colour(i); })
        : (entry.colour || colour(index));
      return {
        label: entry.name,
        data: entry.data,
        backgroundColor: paint,
        borderColor: paint,
        borderWidth: 0,
        borderRadius: 0,
        borderSkipped: false,
        categoryPercentage: 0.74,
        barPercentage: 0.76,
      };
    });
  }

  function slices(values) {
    return {
      data: values,
      backgroundColor: values.map(function (_, index) { return colour(index); }),
      borderColor: '#ffffff',
      borderWidth: 1,
    };
  }

  function numberFigures() {
    var captions = document.querySelectorAll('[data-figure]');
    Array.prototype.forEach.call(captions, function (caption, index) {
      if (caption.dataset.figure === 'done') return;
      var label = document.createElement('strong');
      label.textContent = 'Figure ' + (index + 1) + '.';
      caption.insertBefore(document.createTextNode(' '), caption.firstChild);
      caption.insertBefore(label, caption.firstChild);
      caption.dataset.figure = 'done';
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', numberFigures);
  } else {
    numberFigures();
  }

  window.ExcelChart = {
    numberFigures: numberFigures,
    SERIES: SERIES,
    INK: INK,
    RULE: RULE,
    AXIS: AXIS,
    colour: colour,
    options: options,
    bars: bars,
    slices: slices,
    plugin: dataTable,
  };

  if (window.Chart && window.Chart.register) {
    window.Chart.register(dataTable);
    window.Chart.defaults.font = { family: 'inherit', size: 11 };
    window.Chart.defaults.color = INK;
  }
})();
