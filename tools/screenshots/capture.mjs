// node tools/screenshots/capture.mjs <storyboard-name>   (a file under tools/screenshots/storyboards/)
import { runStoryboard } from './lib.mjs';
const name = process.argv[2];
if (!name) { console.error('usage: node tools/screenshots/capture.mjs <storyboard-name>'); process.exit(2); }
const sb = (await import(`./storyboards/${name}.mjs`)).default;
sb.name = name;
await runStoryboard(sb);
