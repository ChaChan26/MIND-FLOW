import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const backendStatic = path.join(__dirname, '../static/assets');
const backendTemplates = path.join(__dirname, '../templates');

// Clean existing assets & ensure directories exist
if (fs.existsSync(backendStatic)) {
  fs.rmSync(backendStatic, { recursive: true, force: true });
}
fs.mkdirSync(backendStatic, { recursive: true });
if (!fs.existsSync(backendTemplates)) fs.mkdirSync(backendTemplates, { recursive: true });

// Copy index.html
fs.copyFileSync(
  path.join(__dirname, 'dist/index.html'),
  path.join(backendTemplates, 'index.html')
);

// Copy assets
const distAssets = path.join(__dirname, 'dist/assets');
if (fs.existsSync(distAssets)) {
  const files = fs.readdirSync(distAssets);
  files.forEach(file => {
    fs.copyFileSync(
      path.join(distAssets, file),
      path.join(backendStatic, file)
    );
  });
}

console.log('✅ Successfully copied frontend build to Flask backend directories!');
