// Compile exact mathematical body layouts, garment colours, sash meshes & badge placements
// directly from SCOUT3D's source of truth (`body.js` + `badgeLayout.js` + `*_rules_v1.0.json`).
import fs from 'fs';
import path from 'path';

const SCOUT3D_ROOT = process.argv[2] || '/tmp/SCOUT3D_ref';
const OUT_DIR = process.argv[3] || path.resolve('assets/scout3d');

const bodyMod = await import(path.join(SCOUT3D_ROOT, 'src/three/body.js'));
const badgeMod = await import(path.join(SCOUT3D_ROOT, 'src/three/badgeLayout.js'));
const picksMod = await import(path.join(SCOUT3D_ROOT, 'src/lib/picks.js'));

const {
  layout, neckerLayout, strapLayout, sashLayout,
  COLOURS, SCOUT_VARIANTS, VENTURE_VARIANTS, LEADER_VARIANTS,
} = bodyMod;
const { placeFor, visible, sashActive, sleevePose, centreLonePair } = badgeMod;
const { resolveArt } = picksMod;

function loadJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(SCOUT3D_ROOT, rel), 'utf8'));
}

const RULES = {
  grasshopper: loadJson('src/data/grasshopper_rules_v1.0.json'),
  cub: loadJson('src/data/cub_rules_v1.0.json'),
  scout: loadJson('src/data/scout_rules_v1.0.json'),
  venture: loadJson('src/data/venture_rules_v1.0.json'),
  rover: loadJson('src/data/rover_rules_v1.0.json'),
  leader: loadJson('src/data/leader_rules_v1.0.json'),
};
const DISTRICTS = loadJson('src/data/districts_v1.0.json');
const PATROLS = loadJson('src/data/patrols_v1.0.json');

// Default picks for dynamic badges (HK Island Region + Wan Chai / Chai Wan or Handbook Example)
const DEFAULT_PICKS = {
  districtId: 'wan_chai',
  patrolId: 'badger',
  meritYear: 2025,
  level: 'group',
  rank: 'sl',
};

// Check if wan_chai exists, fallback to first district in HKIR
let distCheck = picksMod.findDistrict(DISTRICTS, DEFAULT_PICKS.districtId);
if (!distCheck) {
  DEFAULT_PICKS.districtId = DISTRICTS.regions[0].districts[0].id;
}

// Curated authentic Scout proficiency badges (Teaching / Service / Pursuit / Interest)
const SCOUT_PROF_FAVORITES = [
  'profServiceFirstAider',
  'profPursuitCamper',
  'profPursuitPioneer',
  'profPursuitOrienteer',
  'profPursuitMapReader',
  'profPursuitBackwoodsCook',
  'profInterestSwimmer',
  'profInterestCampCook',
  'profInterestCyclist',
  'profInterestPhotographer',
  'profInterestAstronomer',
  'profInterestNaturalist',
];
// Verify all 12 exist in scout_rules; fill any missing from rules
const allScoutProfIds = RULES.scout.badges.filter((b) => b.anchor?.slot === 'profL').map((b) => b.id);
const resolvedProf12 = [];
for (const id of [...SCOUT_PROF_FAVORITES, ...allScoutProfIds]) {
  if (allScoutProfIds.includes(id) && !resolvedProf12.includes(id)) {
    resolvedProf12.push(id);
    if (resolvedProf12.length === 12) break;
  }
}

// Standard presets of turned-on badges per section (100% compliant with SAHK Uniform Handbook)
const SECTION_PROFILES = {
  grasshopper: {
    rulesKey: 'grasshopper',
    bodySection: 'grasshopper',
    variant: {
      shirt: COLOURS.shirt,
      trim: COLOURS.trim,
      leg: COLOURS.trousers,
      sock: '#f4f4f4',
      shoe: COLOURS.shoe,
      belt: null,
      hat: 'cap',
      hatColor: '#1f4e9c',
      necker: '#7b1e2b',
      woggle: '#e9b425',
      longPants: false,
    },
    outfit: { invested: true },
    state: {
      membership: true,
      troop: true,
      district: true,
      meritorious: true,
      progress: 4,
      grasshopperAward: true,
    },
  },
  cub: {
    rulesKey: 'cub',
    bodySection: 'cub',
    variant: {
      shirt: COLOURS.cubShirt,
      leg: COLOURS.cubGreen,
      sock: COLOURS.cubSock,
      shoe: COLOURS.shoeBlack,
      belt: COLOURS.belt,
      buckle: COLOURS.buckle,
      hat: 'cubCap',
      hatColor: COLOURS.capGreen,
      capBadge: '/badges/cub_cap_badge.png',
      necker: '#e9b425',
      woggle: '#2e7d4f',
      longPants: false,
    },
    outfit: { invested: true },
    state: {
      membership: true,
      hongKong: true,
      troop: true,
      region: true,
      district: true,
      meritorious: true,
      progressAward: 'bauhinia',
      scoutLink: true,
      serviceStar: 'two',
      coreSkills: 'gold',
      coreCaring: 'gold',
      coreCommunity: 'gold',
      coreFamily: 'gold',
    },
  },
  scout: {
    rulesKey: 'scout',
    bodySection: 'scout',
    variant: {
      shirt: SCOUT_VARIANTS.land.shirt,
      leg: SCOUT_VARIANTS.land.leg,
      sock: SCOUT_VARIANTS.land.sock,
      shoe: COLOURS.shoeBlack,
      belt: COLOURS.belt,
      buckle: COLOURS.buckle,
      hat: 'beret',
      hatColor: SCOUT_VARIANTS.land.beret,
      capBadge: '/badges/scout_cap_badge.png',
      necker: '#7b1e2b',
      woggle: COLOURS.leather,
      longPants: false,
    },
    outfit: { invested: true, sash: true },
    state: {
      membership: true,
      hongKong: true,
      troop: true,
      region: true,
      district: true,
      patrol: true,
      meritorious: true,
      serviceStar: 'two',
      ventureLink: true,
      emblemBauhinia: true,
      earthTribe: true,
      ...Object.fromEntries(resolvedProf12.map((id) => [id, true])),
    },
    stateNoSash: {
      membership: true,
      hongKong: true,
      troop: true,
      region: true,
      district: true,
      patrol: true,
      meritorious: true,
      serviceStar: 'two',
      ventureLink: true,
      earthTribe: true,
      ...Object.fromEntries(resolvedProf12.slice(0, 5).map((id) => [id, true])),
    },
  },
  sea_scout: {
    rulesKey: 'scout',
    bodySection: 'scout',
    variant: {
      shirt: SCOUT_VARIANTS.sea.shirt,
      leg: SCOUT_VARIANTS.sea.leg,
      sock: SCOUT_VARIANTS.sea.sock,
      shoe: COLOURS.shoeBlack,
      belt: COLOURS.belt,
      buckle: COLOURS.buckle,
      hat: 'seaCap',
      hatColor: COLOURS.seaCapTop,
      capBadge: '/badges/sea_scout_cap_tally.png',
      necker: '#1f4e9c',
      woggle: COLOURS.leather,
      longPants: false,
    },
    outfit: { invested: true, sash: true },
    state: {
      membership: true,
      hongKong: true,
      troop: true,
      region: true,
      district: true,
      patrol: true,
      meritorious: true,
      ventureLink: true,
      ...Object.fromEntries(resolvedProf12.map((id) => [id, true])),
    },
  },
  air_scout: {
    rulesKey: 'scout',
    bodySection: 'scout',
    variant: {
      shirt: SCOUT_VARIANTS.air.shirt,
      leg: SCOUT_VARIANTS.air.leg,
      sock: SCOUT_VARIANTS.air.sock,
      shoe: COLOURS.shoeBlack,
      belt: COLOURS.belt,
      buckle: COLOURS.buckle,
      hat: 'beret',
      hatColor: SCOUT_VARIANTS.air.beret,
      capBadge: '/badges/scout_cap_badge.png',
      necker: '#1f4e9c',
      woggle: COLOURS.leather,
      longPants: false,
    },
    outfit: { invested: true, sash: true },
    state: {
      membership: true,
      hongKong: true,
      troop: true,
      region: true,
      district: true,
      patrol: true,
      meritorious: true,
      ventureLink: true,
      ...Object.fromEntries(resolvedProf12.map((id) => [id, true])),
    },
  },
  venture: {
    rulesKey: 'venture',
    bodySection: 'venture',
    variant: {
      shirt: VENTURE_VARIANTS.land.shirt,
      leg: VENTURE_VARIANTS.land.leg,
      sock: COLOURS.blackSock,
      shoe: COLOURS.shoeBlack,
      belt: COLOURS.belt,
      buckle: COLOURS.buckle,
      hat: 'beret',
      hatColor: VENTURE_VARIANTS.land.beret,
      capBadge: '/badges/scout_cap_badge.png',
      necker: '#7b1e2b',
      woggle: COLOURS.leather,
      longPants: true,
    },
    outfit: { invested: true },
    state: {
      membership: true,
      hongKong: true,
      epaulette: 'venture',
      troop: true,
      region: true,
      district: true,
      meritorious: true,
      ventureAward: 'dragon',
      stageProject: true,
      barProject: true,
      stageService: true,
      barService: true,
    },
  },
  leader: {
    rulesKey: 'leader',
    bodySection: 'leader',
    variant: {
      shirt: LEADER_VARIANTS.land.shirt,
      leg: LEADER_VARIANTS.land.leg,
      sock: COLOURS.blackSock,
      shoe: COLOURS.shoeBlack,
      belt: COLOURS.belt,
      buckle: COLOURS.buckle,
      hat: 'beret',
      hatColor: LEADER_VARIANTS.land.beret,
      capBadge: '/badges/scout_cap_badge.png',
      necker: COLOURS.gilwellNecker,
      woggle: COLOURS.leather,
      longPants: true,
    },
    outfit: { invested: true, uniform: 'u3' },
    state: {
      membership: true,
      hongKong: true,
      troop: true,
      region: true,
      district: true,
      epaulette: true,
      nameTag: true,
      meritorious: true,
    },
  },
};

const neededPngs = new Set([
  '/badges/world_membership.png',
  '/badges/hong_kong_badge.png',
  '/badges/handbook_example_troop.png',
  '/badges/handbook_example_region.png',
  '/badges/handbook_example_district.png',
  '/badges/meritorious_base_blue.png',
  '/badges/scout_cap_badge.png',
  '/badges/cub_cap_badge.png',
  '/badges/sea_scout_cap_tally.png',
  '/badges/venture_epaulette.png',
  '/badges/leader/epaulette_sl.png',
  '/badges/leader/name_tag_example.png',
]);

function resolveBadgeFile(rules, p) {
  if (p.art && !p.art.startsWith('dyn:')) {
    neededPngs.add(p.art);
    return p.art;
  }
  const badgeDef = rules.badges.find((b) => b.id === p.id);
  if (!badgeDef) return '/badges/world_membership.png';
  if (p.id === 'troop') {
    const f = '/badges/handbook_example_troop.png';
    neededPngs.add(f);
    return f;
  }
  if (p.id === 'nameTag') {
    const f = '/badges/leader/name_tag_example.png';
    neededPngs.add(f);
    return f;
  }
  if (p.id === 'meritorious') {
    const f = '/badges/meritorious_base_blue.png';
    neededPngs.add(f);
    return f;
  }
  const r = resolveArt(badgeDef, DEFAULT_PICKS, DISTRICTS, PATROLS);
  const f = r?.file || r?.base || badgeDef.art?.file || '/badges/world_membership.png';
  neededPngs.add(f);
  return f;
}

function compilePlacements(rules, L, outfit, state) {
  const all = placeFor(rules, outfit);
  const sashOn = sashActive(rules, outfit, state);
  const shown = visible(all, state, { invested: true, sash: sashOn, level: 'group' });
  const seamY = L.top - L.shoulderY;
  const sleeveW = L.B.sleeve.w;

  return {
    sashActive: sashOn,
    badges: shown.map((p) => {
      const badgeDef = rules.badges.find((b) => b.id === p.id);
      const artFile = resolveBadgeFile(rules, p);
      const item = {
        key: p.key,
        id: p.id,
        zh: badgeDef?.zh?.name || p.id,
        mount: p.mount, // 'torso' | 'l' | 'r'
        onSash: !!p.onSash,
        facing: p.facing || 'front',
        shape: p.shape,
        w: p.w,
        h: p.h,
        art: artFile.replace(/^\/badges\//, ''),
      };
      if (p.mount === 'torso') {
        item.x = p.x;
        item.y = p.y;
        item.z = p.z;
        item.rotZ = Array.isArray(p.rot) ? p.rot[2] : 0;
        item.rot = p.rot || null;
      } else {
        const sp = sleevePose(p.mount, sleeveW, seamY, p, 0.12);
        item.u = p.u;
        item.v = p.v;
        item.armLocalPos = sp.position; // [x, y, z] relative to shoulder pivot!
        item.armArtRight = sp.artRight;
      }
      return item;
    }),
  };
}

const compiled = {
  meta: {
    source: 'SCOUT3D v1.0 (body.js + badgeLayout.js + *_rules_v1.0.json)',
    unit: 'cm',
    axes: 'Character faces +Z, Wearer LEFT = +X, Wearer RIGHT = -X, Ground = Y=0',
  },
  colours: COLOURS,
  sections: {},
};

for (const [secKey, prof] of Object.entries(SECTION_PROFILES)) {
  const rules = RULES[prof.rulesKey];
  if (prof.variant.capBadge) neededPngs.add(prof.variant.capBadge);
  compiled.sections[secKey] = {
    variant: prof.variant,
    genders: {},
  };
  for (const gKey of ['boy', 'girl']) {
    const L = layout(gKey, prof.bodySection);
    const NK = neckerLayout(L);
    const ST = strapLayout(L);
    const SA = rules.slots?.profL?.sash ? sashLayout(L) : null;
    const outfit = { ...prof.outfit, gender: gKey };
    const mainSet = compilePlacements(rules, L, outfit, prof.state);
    const noSashSet = prof.stateNoSash
      ? compilePlacements(rules, L, { ...outfit, sash: false }, prof.stateNoSash)
      : null;

    compiled.sections[secKey].genders[gKey] = {
      layout: L,
      necker: {
        wogY: NK.wogY,
        front: NK.front,
        tail: NK.tail,
        back: NK.back,
      },
      strap: ST,
      sash: SA
        ? {
            cTop: SA.cTop,
            k: SA.k,
            theta: SA.theta,
            full: SA.full,
            y1: SA.y1,
            y2: SA.y2,
            z: SA.z,
            rotZ: SA.rotZ,
            widthCm: bodyMod.SASH.widthCm,
            edgeCm: bodyMod.SASH.edgeCm,
            endY: bodyMod.SASH.endY,
          }
        : null,
      placements: mainSet,
      placementsNoSash: noSashSet,
    };
  }
}

fs.mkdirSync(path.join(OUT_DIR, 'badges'), { recursive: true });
let copied = 0;
for (const rel of neededPngs) {
  const cleanRel = rel.replace(/^\/badges\//, '');
  const src = path.join(SCOUT3D_ROOT, 'public/badges', cleanRel);
  const dst = path.join(OUT_DIR, 'badges', cleanRel);
  if (fs.existsSync(src)) {
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
    copied++;
  } else {
    console.warn('Missing badge PNG:', src);
  }
}

const outJson = path.join(OUT_DIR, 'scout3d_rig_data.json');
fs.writeFileSync(outJson, JSON.stringify(compiled, null, 2), 'utf8');
console.log(`Compiled ${Object.keys(compiled.sections).length} sections into ${outJson} and copied ${copied} official badge PNGs!`);
