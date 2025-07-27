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
            set({ presets, isLoading: false });
        } catch (error) {
            set({ error: error.message });
        }
    };

    fetchData();
    const saveToServer = async () => {
        try {
            set({ isDirty: false });
            await fetch(baseUrl + '/presets', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(get().presets),
            });
        } catch (error) {
            set({ error: error.message, isDirty: true });
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

    return {
        presets: null,
        isLoading: true,
        isDirty: false,
        error: null,
        save: () => saveToServer(),
        revert: () => {
            set({ presets: originalPresets});
            updateIsDirty(originalPresets);
        },
        getActivePreset: () => get().presets.find(z => z.isActive),
        setActivePreset: (presetName) => {
            var currentPresets = get().presets;
            if (!currentPresets.some(z => z.name == presetName)){
                alert("no preset with name " + presetName);
                return;
            }
            var updatedPresets = currentPresets.map(preset => ({...preset, isActive: preset.name == presetName}));
            set({ presets: updatedPresets});
            updateIsDirty(updatedPresets);
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
        }
    };
});

export default usePresetStore