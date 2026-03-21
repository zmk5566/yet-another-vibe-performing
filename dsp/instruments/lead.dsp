import("stdfaust.lib");

freq = hslider("freq", 440, 100, 2000, 0.1);
cutoff = hslider("cutoff", 2000, 200, 10000, 1);
resonance = hslider("resonance", 0.4, 0, 1, 0.01);
attack = hslider("attack", 0.01, 0.001, 0.5, 0.001);
release_t = hslider("release", 0.3, 0.01, 2.0, 0.01);
gate = button("trigger");

envelope = gate : en.adsr(attack, 0.1, 0.7, release_t);
process = os.sawtooth(freq) : fi.resonlp(cutoff, resonance, 1) * envelope * 0.4;
