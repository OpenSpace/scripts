'use strict'
const readline = require("readline-sync");
const quat = require('quaternion');
const fs = require('fs');

const PI = Math.PI;
const c1 = 1.70158;
const c2 = c1 * 1.525;
const c3 = c1 + 1;
const c4 = (2 * PI) / 3;
const c5 = (2 * PI) / 4.5;

const bounceOut = function (x) {
	const n1 = 7.5625;
	const d1 = 2.75;

	if (x < 1 / d1) {
		return n1 * x * x;
	} else if (x < 2 / d1) {
		return n1 * (x -= 1.5 / d1) * x + 0.75;
	} else if (x < 2.5 / d1) {
		return n1 * (x -= 2.25 / d1) * x + 0.9375;
	} else {
		return n1 * (x -= 2.625 / d1) * x + 0.984375;
	}
};

const EasingsFunctions = {
	linear: (x) => x,
	easeInQuad: function (x) { return x * x; },
	easeOutQuad: function (x) { return 1 - (1 - x) * (1 - x); },
	easeInOutQuad: function (x) { return x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; },
	easeInCubic: function (x) { return x * x * x; },
	easeOutCubic: function (x) { return 1 - Math.pow(1 - x, 3); },
	easeInOutCubic: function (x) { return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; },
	easeInQuart: function (x) { return x * x * x * x; },
	easeOutQuart: function (x) { return 1 - Math.pow(1 - x, 4); },
	easeInOutQuart: function (x) { return x < 0.5 ? 8 * x * x * x * x : 1 - Math.pow(-2 * x + 2, 4) / 2; },
	easeInQuint: function (x) { return x * x * x * x * x; },
	easeOutQuint: function (x) { return 1 - Math.pow(1 - x, 5); },
	easeInOutQuint: function (x) { return x < 0.5 ? 16 * x * x * x * x * x : 1 - Math.pow(-2 * x + 2, 5) / 2; },
	easeInSine: function (x) { return 1 - Math.cos((x * PI) / 2); },
	easeOutSine: function (x) { return Math.sin((x * PI) / 2); },
	easeInOutSine: function (x) { return -(Math.cos(PI * x) - 1) / 2; },
	easeInExpo: function (x) { return x === 0 ? 0 : Math.pow(2, 10 * x - 10); },
	easeOutExpo: function (x) { return x === 1 ? 1 : 1 - Math.pow(2, -10 * x); },
	easeInOutExpo: function (x) {
		return x === 0
			? 0
			: x === 1
			? 1
			: x < 0.5
			? Math.pow(2, 20 * x - 10) / 2
			: (2 - Math.pow(2, -20 * x + 10)) / 2;
	},
	easeInCirc: function (x) { return 1 - Math.sqrt(1 - Math.pow(x, 2)); },
	easeOutCirc: function (x) { return Math.sqrt(1 - Math.pow(x - 1, 2)); },
	easeInOutCirc: function (x) {
		return x < 0.5
			? (1 - Math.sqrt(1 - Math.pow(2 * x, 2))) / 2
			: (Math.sqrt(1 - Math.pow(-2 * x + 2, 2)) + 1) / 2;
	},
	easeInBack: function (x) {
		return c3 * x * x * x - c1 * x * x;
	},
	easeOutBack: function (x) {
		return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
	},
	easeInOutBack: function (x) {
		return x < 0.5
			? (Math.pow(2 * x, 2) * ((c2 + 1) * 2 * x - c2)) / 2
			: (Math.pow(2 * x - 2, 2) * ((c2 + 1) * (x * 2 - 2) + c2) + 2) / 2;
	},
	easeInElastic: function (x) {
		return x === 0
			? 0
			: x === 1
			? 1
			: -Math.pow(2, 10 * x - 10) * Math.sin((x * 10 - 10.75) * c4);
	},
	easeOutElastic: function (x) {
		return x === 0
			? 0
			: x === 1
			? 1
			: Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * c4) + 1;
	},
	easeInOutElastic: function (x) {
		return x === 0
			? 0
			: x === 1
			? 1
			: x < 0.5
			? -(Math.pow(2, 20 * x - 10) * Math.sin((20 * x - 11.125) * c5)) / 2
			: (Math.pow(2, -20 * x + 10) * Math.sin((20 * x - 11.125) * c5)) / 2 + 1;
	},
	easeInBounce: function (x) {
		return 1 - bounceOut(1 - x);
	},
	easeOutBounce: bounceOut,
	easeInOutBounce: function (x) {
		return x < 0.5
			? (1 - bounceOut(1 - 2 * x)) / 2
			: (1 + bounceOut(2 * x - 1)) / 2;
	},
};


function parse(line) {
  let components = line.split(' ');
  console.assert(components[0] == 'camera');
  console.assert(components.length == 14);

  components[1] = parseFloat(components[1]);
  components[2] = parseFloat(components[2]);
  components[3] = parseFloat(components[3]);
  components[4] = parseFloat(components[4]);
  components[5] = parseFloat(components[5]);
  components[6] = parseFloat(components[6]);
  components[7] = parseFloat(components[7]);
  components[8] = parseFloat(components[8]);
  components[9] = parseFloat(components[9]);
  components[10] = parseFloat(components[10]);
  components[11] = parseFloat(components[11]);

  return {
    osTime: components[1],
    recTime: components[2],
    ingameTime: components[3],
    position: [ components[4], components[5], components[6] ],
    orientation: [ components[7], components[8], components[9], components[10] ],
    scale: components[11],
    follow: components[12],
    node: components[13]
  }
}

function toLine(value) {
  return `camera ${value.osTime} ${value.recTime} ${value.ingameTime} ${value.position[0]} ${value.position[1]} ${value.position[2]} ${value.orientation[0]} ${value.orientation[1]} ${value.orientation[2]} ${value.orientation[3]} ${value.scale} ${value.follow} ${value.node}`;
}

function interp(v1, v2, t, t_prime) {
  let src = new quat.Quaternion(v1.orientation[0], v1.orientation[1], v1.orientation[2], v1.orientation[3]);
  let dst = new quat.Quaternion(v2.orientation[0], v2.orientation[1], v2.orientation[2], v2.orientation[3]);
  let v = src.slerp(dst)(t_prime);

  return {
    osTime: v1.osTime + t * (v2.osTime - v1.osTime),
    recTime: v1.recTime + t * (v2.recTime - v1.recTime),
    ingameTime:  v1.ingameTime + t * (v2.ingameTime - v1.ingameTime),
    position: [
      v1.position[0] + t_prime * (v2.position[0] - v1.position[0]),
      v1.position[1] + t_prime * (v2.position[1] - v1.position[1]),
      v1.position[2] + t_prime * (v2.position[2] - v1.position[2])
    ],
    orientation: [ v['w'], v['x'], v['y'], v['z'] ],
    scale: v1.scale + t_prime * (v2.scale - v1.scale),
    follow: v1.follow,
    node: v1.node
  }
}

let beginLine = readline.question('Begin > ');
let endLine  = readline.question('End   > ');
let interpolationTime = readline.question('Time (optional, seconds) > ');
let easing = readline.question('Easing Func (optional) > ');


let begin = parse(beginLine);
let end = parse(endLine);

// console.assert(begin.recTime < end.recTime);
// console.assert(begin.scale == end.scale);
// console.assert(begin.follow == end.follow);
// console.assert(begin.node == end.node);

if (interpolationTime !== '') {
  let time = parseFloat(interpolationTime);
  end.recTime = begin.recTime + time;
}
if (easing === '') {
  easing = 'easeInOutCubic';
}

console.log(`Using easing function '${easing}'`);

let dt = 1.0 / 10.0;
// let dt = 1.0 / 6.0;

fs.writeFileSync('output.osrectxt', 'OpenSpace_record/playback01.00A\n');
for (let i = begin.recTime; i < end.recTime; i += dt) {
  let t = (i - begin.recTime) / (end.recTime - begin.recTime);

  let t_prime = EasingsFunctions[easing](t);

  let v = interp(begin, end, t, t_prime);
  fs.appendFileSync('output.osrectxt', toLine(v) + '\n');
}
fs.appendFileSync('output.osrectxt', toLine(end));
