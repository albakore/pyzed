// /pyzed/llms-small.txt: the essentials (getting started, tutorials, guides, AI, FAQ) as one file.
import { llmsSmall, textResponse } from '../lib/llms';

export const GET = async () => textResponse(await llmsSmall('en'));
