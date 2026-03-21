import("stdfaust.lib");

freq = hslider("freq", 220, 50, 1000, 0.1);
detune = hslider("detune", 0.3, 0, 1, 0.01);
attack = hslider("attack", 0.3, 0.01, 2.0, 0.01);
release_t = hslider("release", 1.0, 0.1, 5.0, 0.01);
gate = button("trigger");

envelope = gate : en.ar(attack, release_t);
osc1 = os.osc(freq);
osc2 = os.osc(freq * (1 + detune * 0.01));
osc3 = os.osc(freq * (1 - detune * 0.01));
process = (osc1 + osc2 + osc3) / 3 * envelope * 0.4;
