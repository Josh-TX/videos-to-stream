import { create } from 'zustand'

const usePresetStore = create((set, get) => {
    const baseUrl = ""
    var originalPresets = [];
    const fetchData = async () => {
        try {
            var response = await fetch(baseUrl + '/presets');
            var presets = await response.json();
            if (!presets.some(z => z.isActive)){
                presets[0].isActive = true;
            }
            originalPresets = presets;
            set({ presets, isLoading: false, errorGet: null });
        } catch (error) {
            set({ errorGet: error.message });
        }
    };

    fetchData();
    const saveToServer = async () => {
        try {
            var newPresets = get().presets
            set({ isDirty: false, saveBtn: "Saving" });
            await fetch(baseUrl + '/presets', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newPresets),
            });
            set({ saveBtn: "Saved!" });
            originalPresets = newPresets
            setTimeout(() => {
                set({ saveBtn: "Save" });
            }, 1000)
            window.dispatchEvent(new CustomEvent('collapse-all-settings'));
        } catch (error) {
            set({ errorSave: error.message, isDirty: true, saveBtn: "Save" });
            setTimeout(() => {
                 set({ errorSave: null});
            }, 4000)
        }
    }
    const updateIsDirty = (updatedPresets) => {
        if (originalPresets.length != updatedPresets.length){
            set({ isDirty: true});
            return;
        }
        for (var i = 0; i < originalPresets.length; i++){
            for (var key in originalPresets[i]){
                if (originalPresets[i][key] != updatedPresets[i][key]){
                    set({ isDirty: true});
                    return;
                }
            }
        }
        set({ isDirty: false});
    }
    const algorithmSettingNames = ["BASE_DIRECTORY", "EXCLUDE_STARTSWITH_CSV", "EXCLUDE_CONTAINS_CSV", "EXCLUDE_NOTSTARTSWITH_CSV", 
        "EXCLUDE_NOTCONTAINS_CSV", "BOOSTED_STARTSWITH_CSV", "BOOSTED_CONTAINS_CSV", "BOOSTED_NOTSTARTSWITH_CSV", "BOOSTED_NOTCONTAINS_CSV",
        "SUPPRESSED_STARTSWITH_CSV", "SUPPRESSED_CONTAINS_CSV", "SUPPRESSED_NOTSTARTSWITH_CSV", "SUPPRESSED_NOTCONTAINS_CSV"
    ]

    return {
        presets: null,
        isLoading: true,
        saveBtn: "Save",
        isDirty: false,
        errorGet: null,
        errorSave: null,
        save: () => saveToServer(),
        revert: () => {
            set({ presets: originalPresets});
            updateIsDirty(originalPresets);
        },
        getActivePreset: () => get().presets.find(z => z.isActive),
        getActiveAlgoPreset: () => {
            var activePreset = get().presets.find(z => z.isActive);
            var res = {};
            algorithmSettingNames.forEach(key => {
                if (activePreset[key]){
                    res[key]=activePreset[key];
                }
            });
            return res;
        },
        setActivePreset: (presetName) => {
            var currentPresets = get().presets;
            if (!currentPresets.some(z => z.name == presetName)){
                alert("no preset with name " + presetName);
                return;
            }
            var updatedPresets = currentPresets.map(preset => ({...preset, isActive: preset.name == presetName}));
            set({ presets: updatedPresets});
            updateIsDirty(updatedPresets);
            window.dispatchEvent(new CustomEvent('collapse-all-settings'));
        },
        anyAlgoSettings: () => {
            var activePreset = get().presets.find(z => z.isActive)
            return algorithmSettingNames.some(z => activePreset[z])
        },
        clearAlgorithmSettings: () => {
            var presets = [...get().presets];
            var activeIndex = get().presets.findIndex(z => z.isActive)
            presets[activeIndex] = { ...presets[activeIndex] }
            algorithmSettingNames.forEach(settingName => {
                presets[activeIndex][settingName] = ""
            });
            set({ presets: presets});
            updateIsDirty(presets);
        },
        settingChanged: (settingName, newValue) => {
            var presets = [...get().presets];
            var activeIndex = get().presets.findIndex(z => z.isActive)
            presets[activeIndex] = { ...presets[activeIndex] }
            presets[activeIndex][settingName] = newValue
            set({ presets: presets});
            updateIsDirty(presets);
        },
        renameActivePreset: () => {
            var currentPresets = get().presets;
            var activePreset = currentPresets.find(z => z.isActive)
            var newName = prompt("enter new name for preset " + activePreset.name, activePreset.name)
            if (!newName){
                return;
            }
            if (currentPresets.some(z => z.name == newName)){
                alert("preset with name " + newName + " already exists");
                return;
            }
            var updatedPresets = currentPresets.map(preset => preset.isActive ? {...preset, name: newName} : preset);
            set({ presets: updatedPresets});
            updateIsDirty(updatedPresets);
        },
        deleteActivePreset: () => {
            var currentPresets = get().presets;
            if (currentPresets.length <= 1){
                alert("cannot delete the last preset");
                return;
            }
            var activePreset = currentPresets.find(z => z.isActive)
            if (!confirm("Delete preset " + activePreset.name + "?")){
                return;
            }
            var updatedPresets = currentPresets.filter(preset => preset != activePreset);
            updatedPresets[0] = {...updatedPresets[0], isActive: true}
            set({ presets: updatedPresets});
            updateIsDirty(updatedPresets);
            window.dispatchEvent(new CustomEvent('collapse-all-settings'));
        },
        duplicateActivePreset: () => {
            var currentPresets = get().presets;
            var activePreset = currentPresets.find(z => z.isActive)
            var newName = prompt("enter new preset name")
            if (!newName){
                return;
            }
            if (currentPresets.some(z => z.name == newName)){
                alert("preset with name " + newName + " already exists");
                return;
            }
            var updatedPresets = [...currentPresets.map(z => ({...z, isActive: false})), {...activePreset, name: newName}]
            set({ presets: updatedPresets});
            updateIsDirty(updatedPresets);
            window.dispatchEvent(new CustomEvent('collapse-all-settings'));
        }
    };
});

export default usePresetStore