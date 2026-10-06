const fs = require('fs');
const path = require('path');

const dirsToScan = [
  path.join(__dirname, 'src', 'app', 'pro-tools'),
  path.join(__dirname, 'src', 'components', 'pro'),
];

function scanDir(dir) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      scanDir(fullPath);
    } else if (fullPath.endsWith('.tsx') || fullPath.endsWith('.ts')) {
      let content = fs.readFileSync(fullPath, 'utf8');
      
      // Replace maximumFractionDigits: 2 with 5
      let newContent = content.replace(/maximumFractionDigits\s*:\s*2/g, 'maximumFractionDigits: 5');
      
      if (newContent !== content) {
        fs.writeFileSync(fullPath, newContent, 'utf8');
        console.log(`Updated: ${fullPath}`);
      }
    }
  }
}

dirsToScan.forEach(scanDir);
console.log('Done!');
