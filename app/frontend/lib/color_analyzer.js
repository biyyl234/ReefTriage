/*
 * color_analyzer.js — ReefTriage Reef Lab on-device coral bleaching estimator.
 *
 * A dependency-free fallback for coral bleaching severity classification in the browser.
 * Uses HSV color-space analysis of an uploaded/drawn image to estimate the fraction of
 * coral tissue that is white/bleached, and maps it to a 0–100% bleaching index plus
 * a 4-class severity label (healthy / mild / moderate / severe).
 *
 * Rationale & model alternatives: see docs/ai_model_research.md. The NOAA YOLO11n-cls
 * ONNX classifier (binary healthy/bleached) is the documented upgrade path; this script
 * is the zero-dependency baseline that works offline without a model download.
 *
 * Calibration: thresholds below were tuned against the four reference images in
 * app/frontend/img/coral/{healthy,mild,moderate,severe}.jpg. Measured scores:
 *   healthy.jpg  ~25%  -> healthy
 *   mild.jpg     ~53%  -> mild
 *   moderate.jpg ~82%  -> moderate
 *   severe.jpg   ~98%  -> severe
 *
 * Usage (classic script):
 *   <script src="lib/color_analyzer.js"></script>
 *   const a = new CoralColorAnalyzer();
 *   const r = await a.analyzeImage(imgElement);
 *   // r.bleachingPercent in [0,100], r.severity in
 *   //   ['healthy','mild','moderate','severe']
 *
 * Usage (ES module):
 *   import { CoralColorAnalyzer } from './color_analyzer.js';
 */

(function (global, factory) {
  if (typeof module === 'object' && typeof module.exports === 'object') {
    module.exports = { CoralColorAnalyzer: factory() };
  } else {
    global.CoralColorAnalyzer = factory();
  }
})(typeof window !== 'undefined' ? window : this, function () {
  'use strict';

  /**
   * Convert RGB (0-255) to HSV.
   * Returns { h: 0-360, s: 0-100, v: 0-100 }.
   */
  function rgbToHsv(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const d = max - min;
    let h = 0;
    if (d !== 0) {
      if (max === r) h = ((g - b) / d) % 6;
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h *= 60;
      if (h < 0) h += 360;
    }
    const s = max === 0 ? 0 : (d / max) * 100;
    const v = max * 100;
    return { h, s, v };
  }

  class CoralColorAnalyzer {
    /**
     * @param {Object} [opts]
     * @param {number} [opts.sampleStride=4]  pixel sampling stride (1 = every pixel, 4 = fast)
     * @param {number} [opts.whiteSMax=25]     saturation ceiling for "white/bleached"
     * @param {number} [opts.whiteVMin=55]     brightness floor for "white/bleached" (0-100)
     * @param {number} [opts.paleSMin=25]     pale/partial bleaching saturation lower bound
     * @param {number} [opts.paleSMax=45]     pale/partial bleaching saturation upper bound
     * @param {number} [opts.paleVMin=45]     pale brightness floor
     * @param {number} [opts.pigmentedSMin=45] saturation above this = pigmented/healthy coral
     * @param {number} [opts.darkVMax=35]     below this = shadow/dead rubble (excluded from denominator)
     */
    constructor(opts) {
      this.opts = Object.assign({
        sampleStride: 4,
        whiteSMax: 25,
        whiteVMin: 55,
        paleSMin: 25,
        paleSMax: 45,
        paleVMin: 45,
        pigmentedSMin: 45,
        darkVMax: 35
      }, opts || {});
    }

    /**
     * Heuristic water/blue-background mask. Pixels that are clearly blue-dominant open water
     * are excluded from the coral-coverage denominator so the bleaching index is not diluted
     * by the surrounding blue. Tuned for shallow tropical reef photography.
     */
    _isWater(r, g, b, hsv) {
      return (b > r + 15 && b > g + 5 && hsv.h >= 180 && hsv.h <= 220 && hsv.v >= 35 && hsv.v <= 90);
    }

    /**
     * Core analysis on an ImageData object.
     * @param {ImageData} imageData
     * @returns {Object} result
     */
    analyzeImageData(imageData) {
      const d = this.opts;
      const px = imageData.data;
      const w = imageData.width, h = imageData.height;

      let nWhite = 0, nPale = 0, nPigmented = 0, nDark = 0, nWater = 0, nOther = 0;
      let sumSat = 0, sumVal = 0, coralPix = 0;

      for (let y = 0; y < h; y += d.sampleStride) {
        for (let x = 0; x < w; x += d.sampleStride) {
          const i = (y * w + x) * 4;
          const r = px[i], g = px[i + 1], b = px[i + 2], a = px[i + 3];
          if (a < 10) { nOther++; continue; }
          const hsv = rgbToHsv(r, g, b);

          if (this._isWater(r, g, b, hsv)) { nWater++; continue; }

          // coral candidate (non-water)
          coralPix++;
          sumSat += hsv.s; sumVal += hsv.v;

          if (hsv.v < d.darkVMax) { nDark++; }
          else if (hsv.s < d.whiteSMax && hsv.v >= d.whiteVMin) { nWhite++; }
          else if (hsv.s >= d.paleSMin && hsv.s <= d.paleSMax && hsv.v >= d.paleVMin) { nPale++; }
          else if (hsv.s > d.pigmentedSMin) { nPigmented++; }
          else { nOther++; }
        }
      }

      // Bleaching score: white = 1.0, pale = 0.5, pigmented = 0.
      // Dark pixels (shadows / dead rubble) are excluded from the denominator because they
      // are not diagnostic of active bleaching without context.
      const diagnostic = nWhite + nPale + nPigmented;
      const bleachWeight = diagnostic > 0
        ? (nWhite * 1.0 + nPale * 0.5) / diagnostic
        : 0;
      const bleachingPercent = Math.round(Math.min(100, Math.max(0, bleachWeight * 100)) * 10) / 10;

      let severity = 'healthy';
      if (bleachingPercent >= 85) severity = 'severe';
      else if (bleachingPercent >= 60) severity = 'moderate';
      else if (bleachingPercent >= 30) severity = 'mild';

      const totalCoral = nWhite + nPale + nPigmented + nDark + nOther || 1;
      return {
        bleachingPercent,
        severity,
        counts: {
          white: nWhite, pale: nPale, pigmented: nPigmented,
          dark: nDark, water: nWater, other: nOther, coral: totalCoral
        },
        fractions: {
          white: round2(nWhite / totalCoral),
          pale: round2(nPale / totalCoral),
          pigmented: round2(nPigmented / totalCoral),
          dark: round2(nDark / totalCoral),
          water: round2(nWater / (nWater + totalCoral))
        },
        meanSaturation: coralPix ? round2(sumSat / coralPix) : 0,
        meanValue: coralPix ? round2(sumVal / coralPix) : 0,
        calibration: {
          note: 'HSV-based heuristic; calibrated against app/frontend/img/coral/{healthy,mild,moderate,severe}.jpg. ' +
                'Measured reference scores: healthy~25%, mild~53%, moderate~82%, severe~98%.',
          thresholds: {
            white: { sMax: d.whiteSMax, vMin: d.whiteVMin },
            pale:  { sMin: d.paleSMin, sMax: d.paleSMax, vMin: d.paleVMin },
            pigmented: { sMin: d.pigmentedSMin },
            dark:  { vMax: d.darkVMax }
          },
          classBreaks: { healthy: '<30%', mild: '30-60%', moderate: '60-85%', severe: '>=85%' }
        }
      };
    }

    /**
     * Analyze a canvas element directly.
     * @param {HTMLCanvasElement} canvas
     * @param {Object} [opts]  {maxSize} will downscale for speed if provided.
     */
    analyzeCanvas(canvas, opts) {
      const maxSize = (opts && opts.maxSize) || 480;
      let src = canvas;
      if (canvas.width > maxSize || canvas.height > maxSize) {
        const scale = maxSize / Math.max(canvas.width, canvas.height);
        const tmp = document.createElement('canvas');
        tmp.width = Math.round(canvas.width * scale);
        tmp.height = Math.round(canvas.height * scale);
        tmp.getContext('2d').drawImage(canvas, 0, 0, tmp.width, tmp.height);
        src = tmp;
      }
      const sctx = src.getContext('2d', { willReadFrequently: true });
      const imageData = sctx.getImageData(0, 0, src.width, src.height);
      return this.analyzeImageData(imageData);
    }

    /**
     * Analyze an HTMLImageElement / ImageBitmap / Blob URL.
     * Draws the image to an offscreen canvas, then runs analyzeCanvas.
     * @param {HTMLImageElement|ImageBitmap|string} img
     * @returns {Promise<Object>}
     */
    analyzeImage(img) {
      const self = this;
      return new Promise((resolve, reject) => {
        const load = (image) => {
          const c = document.createElement('canvas');
          c.width = image.naturalWidth || image.width;
          c.height = image.naturalHeight || image.height;
          c.getContext('2d').drawImage(image, 0, 0);
          resolve(self.analyzeCanvas(c));
        };
        if (typeof img === 'string') {
          const im = new Image();
          im.crossOrigin = 'anonymous';
          im.onload = () => load(im);
          im.onerror = (e) => reject(e);
          im.src = img;
        } else if (typeof HTMLImageElement !== 'undefined' && img instanceof HTMLImageElement) {
          load(img);
        } else if (typeof ImageBitmap !== 'undefined' && img instanceof ImageBitmap) {
          load(img);
        } else {
          reject(new Error('analyzeImage expects an HTMLImageElement, ImageBitmap, or URL string'));
        }
      });
    }
  }

  function round2(x) { return Math.round(x * 100) / 100; }

  return CoralColorAnalyzer;
});
