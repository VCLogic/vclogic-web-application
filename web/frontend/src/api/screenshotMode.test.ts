import { afterEach, expect, it, vi } from 'vitest';
import { createScreenshotMask, screenshotMode } from './screenshotMode';
import { api } from './client';

afterEach(() => { sessionStorage.clear(); window.history.replaceState({}, '', '/'); vi.unstubAllGlobals(); });

it('masks names, firms, nested narratives, URLs, portraits and investor keys without changing inputs', () => {
  const mask = createScreenshotMask([{vc_slug:'example-person',display_name:'Example Person-like Investor',firm:'Sample Ventures'}]);
  const original = {vc_slug:'example-person',display_name:'Example Person-like Investor',firm:'Sample Ventures',portrait_path:'/private.jpg',source_url:'https://example.org/private',body:'Person and Example at Sample Ventures. [Source](https://example.org/person)',versions:{'example-person':'version-id'}};
  const result = mask.mask(original);
  expect(result).toMatchObject({vc_slug:'investor-1',display_name:'Investor #1',firm:'Investment firm',portrait_path:'/investor-placeholder.svg',source_url:'',versions:{'investor-1':'version-id'}});
  expect(result.body).not.toMatch(/Example|Person|Sample Ventures|https:/);
  expect(original.portrait_path).toBe('/private.jpg');
  expect(mask.originalPath('/api/investors/investor-1/chapters/persona.md')).toBe('/api/investors/example-person/chapters/persona.md');
});

it('assigns deterministic aliases regardless of endpoint ordering', () => {
  const rows=[{vc_slug:'z-person',display_name:'Zed Person'},{vc_slug:'a-person',display_name:'Alpha Person'}];
  expect(createScreenshotMask(rows).mask(rows)).toEqual(createScreenshotMask([...rows].reverse()).mask(rows));
});

it('persists mode across navigation and explicitly exits', () => {
  window.history.replaceState({}, '', '/?screenshots=1'); expect(screenshotMode()).toBe(true);
  window.history.replaceState({}, '', '/pitches'); expect(screenshotMode()).toBe(true);
  window.history.replaceState({}, '', '/?screenshots=0'); expect(screenshotMode()).toBe(false);
});

it('masks saved assessment narratives and translates alias routes back for reads', async () => {
  window.history.replaceState({}, '', '/?screenshots=1');
  const identities = {investors:[{vc_slug:'example-person',display_name:'Example Person',firm:'Sample Ventures'}]};
  const fetch=vi.fn().mockImplementation((path:string) => Promise.resolve(new Response(JSON.stringify(
    path === '/api/investors/identities'
      ? identities : {vc_slug:'example-person',decision_summary:'Example Person at Sample Ventures would invest.',citations:[{title:'Person interview',source_url:'https://example.org/person'}]},
  ))));
  vi.stubGlobal('fetch',fetch);
  const result=await api.assessment('saved-assessment');
  expect(result.decision_summary).toBe('Investor #1 at Investment firm would invest.');
  expect(result.citations?.[0].source_url).toBe('');
  await api.profile('investor-1');
  expect(fetch).toHaveBeenLastCalledWith('/api/investors/example-person',expect.anything());
});


it('masks a firm encoded in the investor slug when wiki firm metadata is empty', () => {
  const mask = createScreenshotMask([{vc_slug:'avery-reed-bright-ideas-group',display_name:'Avery Reed',firm:''}]);
  expect(mask.mask({summary:'Avery Reed founded Bright Ideas Group.', body:'BRIGHT IDEAS GROUP and bright-ideas-group', firm:'Bright Ideas Group'})).toEqual({
    summary:'Investor #1 founded Investment firm.', body:'Investment firm and Investment firm', firm:'Investment firm',
  });
});

it('retains firm aliases from duplicate identities with less complete metadata', () => {
  const mask = createScreenshotMask([
    {vc_slug:'avery-reed',display_name:'Avery Reed',firm:'Example Capital'},
    {vc_slug:'avery-reed',display_name:'Avery Reed',firm:''},
  ]);
  expect(mask.mask('Example Capital')).toBe('Investment firm');
});


it('supports anonymous-mode actions while translating only exact investor identifiers', async () => {
  window.history.replaceState({}, '', '/?anonymous=1');
  const fetch=vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch',fetch);
  await api.startAssessment('project','version','investor-1','version-hash');
  expect(fetch).toHaveBeenLastCalledWith('/api/projects/project/versions/version/assessments',expect.objectContaining({method:'POST',body:JSON.stringify({vc_slug:'example-person',investor_version_id:'version-hash',authorize_provider_cost:true})}));
  const presentation=createScreenshotMask([{vc_slug:'example-person',display_name:'Example Person'}]);
  expect(presentation.originalData({selected:['investor-1'],versions:{'investor-1':'hash'},answer:'Ask investor-1 about the pitch.'})).toEqual({selected:['example-person'],versions:{'example-person':'hash'},answer:'Ask investor-1 about the pitch.'});
});
