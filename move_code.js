const fs = require('fs');
let code = fs.readFileSync('frontend/src/app/whale-tracker/page.tsx', 'utf8');

// Find all useState and useRef declarations and move them to the top of App()
// We'll extract the block of states, remove them, and inject them at the start.

const stateBlockRegex = /const \[activeTab, setActiveTab.*?const \[copiedText, setCopiedText\] = useState\(null\);/s;
const stateMatch = code.match(stateBlockRegex);

if (stateMatch) {
    const states = stateMatch[0];
    code = code.replace(states, '');

    const insertPoint = "const API_BASE";
    code = code.replace(insertPoint, states + "\n\n  " + insertPoint);
    
    fs.writeFileSync('frontend/src/app/whale-tracker/page.tsx', code, 'utf8');
    console.log("Moved states block up successfully!");
} else {
    console.error("Could not find the states block to move.");
}
