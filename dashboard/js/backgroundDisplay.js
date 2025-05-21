const canvas = document.getElementById('bee-bg');
const ctx = canvas.getContext('2d');

function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
resize();

window.addEventListener('resize', resize);

// SVG Images 2 B64
const beeImg = new Image();
beeImg.src = 'data:image/svg+xml;base64,' + btoa(`
<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 64 64">
  <ellipse cx="32" cy="40" rx="18" ry="10" fill="#EC3A3A" stroke="#000" stroke-width="2"/>
  <ellipse cx="32" cy="32" rx="14" ry="18" fill="#F17878" stroke="#000" stroke-width="2"/>
  <ellipse cx="24" cy="28" rx="6" ry="10" fill="#FFF" fill-opacity="0.7"/>
  <ellipse cx="40" cy="28" rx="6" ry="10" fill="#FFF" fill-opacity="0.7"/>
  <ellipse cx="32" cy="32" rx="14" ry="18" fill="none" stroke="#000" stroke-width="2"/>
  <rect x="18" y="32" width="28" height="6" rx="3" fill="#000" opacity="0.2"/>
  <ellipse cx="32" cy="50" rx="4" ry="2" fill="#000"/>
  <ellipse cx="32" cy="18" rx="4" ry="2" fill="#000"/>
  <rect x="28" y="10" width="8" height="8" rx="4" fill="#000"/>
  <rect x="30" y="6" width="4" height="8" rx="2" fill="#000"/>
</svg>
`);

const potImg = new Image();
potImg.src = 'data:image/svg+xml;base64,' + btoa(`
<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 64 64">
  <rect x="15" y="20" width="34" height="30" rx="8" ry="8" fill="#35B93E" stroke="#FFC107" stroke-width="3"/>
  <ellipse cx="32" cy="20" rx="17" ry="8" fill="#B8860B" stroke="#B8860B" stroke-width="3"/>
  <circle cx="32" cy="35" r="6" fill="#BEDEC0" opacity="0.6"/>
</svg>
`);

// Bee class
class Bee {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = 20 + Math.random() * 10;
        this.speedX = (Math.random() - 0.5) * 1.5;
        this.speedY = (Math.random() - 0.5) * 1.5;
        this.angle = Math.random() * 2 * Math.PI;
        this.angleSpeed = (Math.random() - 0.5) * 0.05;
    }
    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        this.angle += this.angleSpeed;

        if (this.x < 0 || this.x > canvas.width) this.speedX *= -1;
        if (this.y < 0 || this.y > canvas.height) this.speedY *= -1;
    }
    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.angle);
        ctx.drawImage(beeImg, -this.size/2, -this.size/2, this.size, this.size);
        ctx.restore();
    }
}

// Honeypot class
class HoneyPot {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = 30 + Math.random() * 20;
        this.opacity = 0;
        this.opacitySpeed = 0.01 + Math.random() * 0.02;
        this.visible = true;
    }
    update() {
        if (this.visible) {
            this.opacity += this.opacitySpeed;
            if (this.opacity >= 1) {
                this.opacity = 1;
                this.visible = false;
            }
        } else {
            this.opacity -= this.opacitySpeed;
            if (this.opacity <= 0) {
                this.opacity = 0;
                this.visible = true;
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
            }
        }
    }
    draw() {
        ctx.save();
        ctx.globalAlpha = this.opacity;
        ctx.drawImage(potImg, this.x - this.size/2, this.y - this.size/2, this.size, this.size);
        ctx.restore();
    }
}

const bees = [];
const honeyPots = [];
const NUM_BEES = 25;
const NUM_POTS = 8;

for(let i=0; i<NUM_BEES; i++) bees.push(new Bee());
for(let i=0; i<NUM_POTS; i++) honeyPots.push(new HoneyPot());

// Animation
function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const gradient = ctx.createRadialGradient(canvas.width/2, canvas.height/2, 100, canvas.width/2, canvas.height/2, canvas.width);
    gradient.addColorStop(0, '#000000');
    gradient.addColorStop(1, '#000000');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    honeyPots.forEach(pot => {
        pot.update();
        pot.draw();
    });

    bees.forEach(bee => {
        bee.update();
        bee.draw();
    });

    requestAnimationFrame(animate);
}


let imagesLoaded = 0;
[beeImg, potImg].forEach(img => {
    img.onload = () => {
        imagesLoaded++;
        if(imagesLoaded === 2) animate();
    }
});
